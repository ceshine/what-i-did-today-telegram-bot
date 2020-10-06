FROM python:3.7

ADD requirements.txt .
RUN pip install --no-cache -r requirements.txt

COPY widt /src/widt
COPY keyfile.json /src/
WORKDIR /src/
CMD ["python", "-m", "widt.bot"]
