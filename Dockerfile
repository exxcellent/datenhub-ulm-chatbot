FROM rasa/rasa-sdk:2.8.3

USER root

COPY requirements.txt requirements.txt

RUN pip install -r requirements.txt

USER 1001