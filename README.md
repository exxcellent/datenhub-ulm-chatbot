# MA Fabian Lette Chatbot

## Deployment

Go to the directory where the docker-compose file is placed.

Be sure that all files in the bot folder belong to the user rasa.

    sudo adduser rasa
    sudo chown -R rasa:rasa bot

Start the docker compose:

    docker-compose up --build

The Rasa Server will start, but it will notify, that no model was found. To generate a model open a new CLI and run:

    docker exec <name_of_rasa_docker_container> rasa train

Shut the servers down (Ctrl + C) and restart them (docker-compose up). Now the trained model will be used.

## Usage

Open in browser of choice:

    localhost:80