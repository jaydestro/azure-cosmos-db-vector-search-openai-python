# Search the baseballplayers index.
#
# Chris Joakim, Microsoft

New-Item -ItemType Directory -Force -Path .\tmp | out-null

# python cogsearch_main.py search_index baseballplayers all_players 

python cogsearch_main.py search_index baseballplayers aaronha01

python cogsearch_main.py vector_search_like baseballplayers aaronha01
python cogsearch_main.py vector_search_like baseballplayers jeterde01
python cogsearch_main.py vector_search_like baseballplayers henderi01
python cogsearch_main.py vector_search_like baseballplayers blombro01
python cogsearch_main.py vector_search_like baseballplayers guidrro01
python cogsearch_main.py vector_search_like baseballplayers rosepe01

echo 'done'
