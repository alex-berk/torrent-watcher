FROM python:3.11.1
WORKDIR /usr/
COPY . .
RUN pip install pipenv
RUN pipenv sync
CMD [ "pipenv", "run", "python", "./main.py" ]
