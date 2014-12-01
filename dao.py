from pymongo import MongoClient, DESCENDING
from bson.objectid import ObjectId
from datetime import datetime, timedelta
from model import *
import re
import trueskill

DEFAULT_RATING = TrueskillRating()
DATABASE_NAME = 'garpr'
PLAYERS_COLLECTION_NAME = 'players'
TOURNAMENTS_COLLECTION_NAME = 'tournaments'
PENDING_TOURNAMENTS_COLLECTION_NAME = 'pending_tournaments'
RANKINGS_COLLECTION_NAME = 'rankings'
REGIONS_COLLECTION_NAME = 'regions'

class RegionNotFoundException(Exception):
    pass

class DuplicateAliasException(Exception):
    pass

class InvalidNameException(Exception):
    pass

#TODO create RegionSpecificDao object
class Dao(object):
    def __init__(self, region_id, mongo_client):
        self.mongo_client = mongo_client
        self.region_id = region_id

        if not region_id in [r.id for r in Dao.get_all_regions(mongo_client=self.mongo_client)]:
            raise RegionNotFoundException("%s is not a valid region id!" % region_id)

        self.players_col = mongo_client[DATABASE_NAME][PLAYERS_COLLECTION_NAME]
        self.tournaments_col = mongo_client[DATABASE_NAME][TOURNAMENTS_COLLECTION_NAME]
        self.pending_tournaments_col = mongo_client[DATABASE_NAME][PENDING_TOURNAMENTS_COLLECTION_NAME]
        self.rankings_col = mongo_client[DATABASE_NAME][RANKINGS_COLLECTION_NAME]

    @classmethod
    def insert_region(cls, region, mongo_client):
        return mongo_client[DATABASE_NAME][REGIONS_COLLECTION_NAME].insert(region.get_json_dict())

    # sorted by display name
    @classmethod
    def get_all_regions(cls, mongo_client):
        regions = [Region.from_json(r) for r in mongo_client[DATABASE_NAME][REGIONS_COLLECTION_NAME].find()]
        return sorted(regions, key=lambda r: r.display_name)

    def get_player_by_id(self, id):
        '''id must be an ObjectId'''
        return Player.from_json(self.players_col.find_one({'_id': id}))

    def get_player_by_alias(self, alias):
        '''Converts alias to lowercase'''
        return Player.from_json(self.players_col.find_one({
            'aliases': {'$in': [alias.lower()]}, 
            'regions': {'$in': [self.region_id]}
        }))

    def get_players_by_alias_from_all_regions(self, alias):
        '''Converts alias to lowercase'''
        return [Player.from_json(p) for p in self.players_col.find({'aliases': {'$in': [alias.lower()]}})]

    special_chars = re.compile("[^\w\s]*")
    def get_player_jsons_with_similar_alias_from_all_regions(self, alias):
        alias_lower = alias.lower()
        similar_aliases = [
            alias_lower,
            alias_lower.replace(" ", ""), # remove spaces
            re.sub(special_chars, '', alias_lower), # remove special characters
            # remove everything before the last special character; hopefully removes crew/sponsor tags
            re.split(special_chars, alias_lower)[-1].strip()
        ]
        return self.players_col.find({'aliases': {'$in': similar_aliases}})

    def get_players_with_similar_alias_from_all_regions(self, alias):
        return [Player.from_json(self.get_player_jsons_with_similar_alias_from_all_regions)]

    def get_player_id_map_from_player_aliases(self, aliases):
        '''Given a list of player aliases, returns a map that maps player aliases -> player ids for the current
        region. If no player can be found, returns a map from alias -> None.'''
        player_alias_to_player_id_map = {}

        for alias in aliases:
            id = None
            player = self.get_player_by_alias(alias)
            if player is not None:
                id = player.id

            player_alias_to_player_id_map[alias] = id

        return player_alias_to_player_id_map

    # give suggestions (in the form of Player jsons) for unknown aliases
    def get_player_suggestions_from_player_aliases(self, aliases):
        alias_to_suggestion_map = {}

        for alias in aliases:
            player = self.get_player_by_alias(alias)
            if player is None:
                alias_to_suggestion_map[alias] = self.get_players_jsons_with_similar_alias_from_all_regions(alias)

        return alias_to_suggestion_map

    def get_player_or_suggestions_from_player_aliases(self, aliases):
        alias_to_player_or_suggestions_map = {}

        for alias in aliases:
            player = self.get_player_by_alias(alias)
            if player is None:
                alias_to_player_or_suggestions_map[alias] = {
                    "player": None,
                    "suggestions": self.get_players_jsons_with_similar_alias_from_all_regions(alias)
                }
            else:
                alias_to_player_or_suggestions_map[alias] = {"player": player, "suggestions": []}

        return alias_to_player_or_suggestions_map

    # TODO this currently gets players for the current region.
    # TODO add another function that explicitly gets all players in the db
    def get_all_players(self):
        '''Sorts by name in lexographical order'''
        return [Player.from_json(p) for p in self.players_col.find({'regions': {'$in': [self.region_id]}}).sort([('name', 1)])]

    def insert_player(self, player):
        return self.players_col.insert(player.get_json_dict())

    def delete_player(self, player):
        return self.players_col.remove({'_id': player.id})

    def update_player(self, player):
        return self.players_col.update({'_id': player.id}, player.get_json_dict())

    # TODO bulk update
    def update_players(self, players):
        pass

    def add_alias_to_player(self, player, alias):
        lowercase_alias = alias.lower()

        if lowercase_alias in player.aliases:
            raise DuplicateAliasException('%s is already an alias for %s!' % (alias, player.name))

        player.aliases.append(lowercase_alias)

        return self.update_player(player)

    def update_player_name(self, player, name):
        # ensure this name is already an alias
        if not name.lower() in player.aliases:
            raise InvalidNameException(
                    'Player %s does not have %s as an alias already, cannot change name.' 
                    % (player, name))

        player.name = name
        return self.update_player(player)

    def insert_pending_tournament(self, tournament):
        return self.pending_tournaments_col.insert({'tournament': tournament.get_json_dict()})

    def update_pending_tournament(self, tournament):
        return self.pending_tournaments_col.update({'_id': tournament.id}, tournament.get_json_dict())

    def get_all_pending_tournament_jsons(self, regions=None):
        query_dict = {'regions': {'$in': regions}} if regions else {}
        return self.pending_tournaments_col.find(query_dict).sort([('date', 1)])

    def get_all_pending_tournaments(self, regions=None):
        return [PendingTournament.from_json(t) for t in self.get_all_pending_tournament_jsons(regions)]

    def get_pending_tournament_by_id(self, id):
        '''id must be an ObjectId'''
        return PendingTournament.from_json(self.pending_tournaments_col.find_one({'_id': id}))

    def insert_tournament(self, tournament):
        return self.tournaments_col.insert(tournament.get_json_dict())

    def update_tournament(self, tournament):
        return self.tournaments_col.update({'_id': tournament.id}, tournament.get_json_dict())

    def get_all_tournament_records(self, players=None, regions=None):
        '''players is a list of Players'''
        query_dict = {}
        query_list = []

        if players:
            for player in players:
                query_list.append({'players': {'$in': [player.id]}})

        if regions:
            query_list.append({'regions': {'$in': regions}})

        if query_list:
            query_dict['$and'] = query_list

        return self.tournaments_col.find(query_dict, {'_id': 1}).sort([('date', 1)])

    def get_all_tournament_ids(self, players=None, regions=None):
        return [t['_id'] for t in self.get_all_tournament_records(players, regions)]

    def get_all_tournaments(self, players=None, regions=None):
        return [Tournament.from_json(t) for t in self.get_all_tournament_records(players, regions)]

    def get_tournament_by_id(self, id):
        '''id must be an ObjectId'''
        return Tournament.from_json(self.tournaments_col.find_one({'_id': id}))

    # TODO reduce db calls for this
    def merge_players(self, source=None, target=None):
        if source is None or target is None:
            raise TypeError("source or target can't be none!");

        if source == target:
            raise ValueError("source and target can't be the same!")

        target.merge_with_player(source)
        self.update_player(target)

        for tournament_id in self.get_all_tournament_ids():
            tournament = self.get_tournament_by_id(tournament_id)
            tournament.replace_player(player_to_remove=source, player_to_add=target)
            self.update_tournament(tournament)

        self.delete_player(source)

    def insert_ranking(self, ranking):
        return self.rankings_col.insert(ranking.get_json_dict())

    def get_latest_ranking(self):
        return Ranking.from_json(self.rankings_col.find({'region': self.region_id}).sort('time', DESCENDING)[0])

    # TODO this is untested
    def is_inactive(self, player, now):
        # default rules
        day_limit = 45
        num_tourneys = 1

        # special case for NYC
        # TODO this goes away once regions become a db collection
        if self.region_id == "nyc":
            day_limit = 90
            num_tourneys = 3

        qualifying_tournaments = [x for x in self.get_all_tournaments(players=[player], regions=[self.region_id]) if x.date >= (now - timedelta(days=day_limit))]
        if len(qualifying_tournaments) >= num_tourneys:
            return False
        return True
