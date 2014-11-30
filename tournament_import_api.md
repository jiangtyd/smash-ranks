# Tournament Import API

##Upload bracket: 
 - `POST /[region]/tournament/`
    - Body: Tourney name; Bracket type; Challonge link or (TIO file contents and bracket name)
    - for TIO: save into tmp directory
    - insert pickle of `Scraper` into `pending_scrapers` collection
    - for TIO: delete file in tmp directory
    - return: 
        ```
        {
          id: ObjectId of Scraper,
          unknown_aliases: [ 
            { alias: "", suggestions: [] }
          ],
          players_in_region: [] // actually just a list of aliases of players
        }
        ```

##Merge aliases:
 - `POST /[region]/tournament/aliases`
    - body: `{ scraper_id: scraper_id, new_aliases: [ { new_player: bool, alias: ""} ] }`
    - for each unknown player: if new, create new player with given alias. otherwise, merge player.
    - Put all these into a map (`alias -> player id`). Extend this map with known players.
    - create new `Tournament` object out of unpickled `Scraper` + (`alias -> player id`) map.
    - save `Tournament` to `pending_tournaments` collection. delete used `Scraper` from `pending_scrapers`.
    - return success

##Manual cleanup: 
Probably...
  - `DELETE /[region]/tournaments/pending/[tournament_id]/[match_id]`
  - `POST /[region]/player/[player_id]/merge` (body: player to merge with)

##List pending brackets:
 - `GET /[region]/tournaments/pending`

##Finalize:
 - `POST /[region]/tournaments/pending/[tournament_id]/finalize`
    - computes new ranking!
