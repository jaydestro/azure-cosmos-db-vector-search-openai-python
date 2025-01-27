# Vectorize the wrangled documents using Azure OpenAI.
# Chris Joakim, Microsoft, 2023

mkdir .\tmp -Force | Out-Null

python .\bb_wrangle.py add_embeddings_to_documents

python .\bb_wrangle.py scan_embeddings

python .\bb_wrangle.py csv_reports

echo 'listing of all tmp files:'
dir tmp\*.*

echo 'done'
