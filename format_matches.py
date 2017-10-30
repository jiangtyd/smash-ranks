def format_match(m):
    return '{} {}-{} {}'.format(m['winner'], m['winnerScore'], m['loserScore'], m['loser'])

def get_main_tag(tag):
    return tag.split('|')[-1].strip()

def get_matches_for_player(player, sgg):
    return map(lambda n: format_match(n),
      filter(lambda m: get_main_tag(player).lower() in (get_main_tag(m['winner']).lower(), get_main_tag(m['loser']).lower()),
          sgg.get_matches_pretty()))
