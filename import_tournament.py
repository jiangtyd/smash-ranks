import click
from scraper.tio import TioScraper
from scraper.challonge import ChallongeScraper
from model import *
from dao import Dao
import rankings
from ConfigParser import ConfigParser
from pymongo import MongoClient
import getpass
from bson.objectid import ObjectId

DEFAULT_RATING = {}

def parse_config():
    config = ConfigParser()
    config.read('config/config.ini')
    return config

def get_dao(region):
    config = parse_config()
    username = config.get('database', 'user')
    host = config.get('database', 'host')
    auth_db = config.get('database', 'auth_db')
    password = getpass.getpass()

    mongo_client = MongoClient(host='mongodb://%s:%s@%s/%s' % (username, password, host, auth_db))
    return Dao(region, mongo_client=mongo_client)

# import pending tournaments
def import_tournament_from_tio_raw(region, raw, bracket, name):
    dao = get_dao(region)
    scraper = TioScraper(raw, bracket)
    pending = PendingTournament.from_scraper(type, scraper, region)
    if name:
        pending.name = name

    dao.insert_pending_tournament(pending)

def import_tournament_from_challonge(region, path, name):
    dao = get_dao(region)
    scraper = ChallongeScraper(path)
    pending = PendingTournament.from_scraper(type, scraper, region)
    if name:
        pending.name = name

    dao.insert_pending_tournament(pending)

# return relevant info about aliases
def get_player_aliases(region, pending_id):
    dao = get_dao(region)

    pending = dao.get_pending_tournament_by_id(ObjectId(pending_id))
    players_in_region = dao.get_all_players()
    player_map = dao.get_player_or_suggestions_from_player_aliases(pending.players)

    return {
        "id": pending.id,
        "player_map": player_map,
        "players_in_region": players_in_region
    }

# update pending tournament's alias_to_id_map
# alias_to_id_map will have "" as the entry if it's a new player
def post_player_aliases(region, pending_id, alias_to_id_map):
    dao = get_dao(region)
    pending = dao.get_pending_tournament_by_id(ObjectId(pending_id))

    for alias in alias_to_id_map:
        player_info = alias_to_id_map[alias]

        if player_info["is_new"]:
            player_regions = [] if player_info["out_of_region"] else [region]
            player_to_add = Player(player_info["name"], [alias, player_info["name"]], DEFAULT_RATING, player_regions)
            new_player_id = dao.insert_player(player_to_add)
            pending.add_alias_id_mapping(alias, new_player_id)
        else:
            player = dao.get_player_by_id(ObjectId(player_info["player_id"]))
            dao.add_alias_to_player(player, alias)
            pending.add_alias_id_mapping(alias, player.id)

def get_pending_tournaments(region):
    dao = get_dao(region)
    return dao.get_all_pending_tournament_jsons([region])

def finalize_tournament(region, pending_tournament):
    dao = get_dao(region)
    if not pending_tournament.are_all_aliases_mapped():
        raise Exception("Not all aliases for the pending tournament have been mapped to an id.")
    tournament = Tournament.from_pending_tournament(pending_tournament)
    dao.insert_tournament(tournament)
    rankings.generate_ranking(dao)

