FROM python:3.7

RUN pip install --no-cache python-telegram-bot==12.0.0 retrying==1.3.3 google-cloud-firestore==1.6.0 ujson==1.35 requests==2.20.1 jinja2==2.10.1

COPY widt /src/widt
COPY keyfile.json /src/
WORKDIR /src/

CMD ["python", "-m", "widt.bot"]
