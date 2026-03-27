# docker exec ollama ollama pull codellama:7b-instruct
# docker exec -it ollama ollama run codellama:7b-instruct /bye

export OLLAMA_API_URL=http://ollama:11434/api/generate

./run-server.sh
