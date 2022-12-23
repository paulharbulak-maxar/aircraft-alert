# aircraft-alert
ADS-B message parser with ability to display aircraft info on LED matrix

## Import aircraft registration CSV file into MongoDB
Download latest CSV file from https://opensky-network.org/datasets/metadata/
```
curl -o aircraftDatabase.csv https://opensky-network.org/datasets/metadata/aircraftDatabase.csv
```

Run MongoDB container and execute _mongoimport_  in container to import:
```
docker run -p 27017:27017 -p 28017:28017 \
-v ${PWD}/aircraftDatabase.csv:/aircraftDatabase.csv \
-v ${PWD}/mongod.conf:/etc/mongod.conf \
--name mongodb -d mongo:latest

docker exec -it mongodb mongoimport --type csv -d adsb -c aircraft \
--headerline --drop aircraftDatabase.csv
```
