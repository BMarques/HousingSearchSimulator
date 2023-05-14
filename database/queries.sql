CREATE DATABASE webmapping;

CREATE SCHEMA postgis;
GRANT USAGE ON schema postgis to public;
CREATE EXTENSION postgis SCHEMA postgis;
ALTER DATABASE webmapping SET search_path=public,postgis,contrib;

SELECT postgis_full_version();

CREATE SCHEMA project;

-- INSERT SCHOOLS INTO DATABASE

CREATE TABLE project.schools
(
	gid integer NOT NULL,
	name character varying(120),
	geom geometry(point, 3763)
);

CREATE INDEX ix_schools
	ON project.schools USING gist(geom)

-- NOT A SQL SCRIPT, SO IT'S GOING TO BE COMMENTED
-- IMPORT SHAPEFILES
-- shp2pgsql -D -s 3763 -g geom -I ./POIEducacao/POIEducacao.shp project.schools_staging | psql -h localhost -U postgres -p 5432 -d webmapping

INSERT INTO project.schools (gid, name, geom)
SELECT gid, nome_escol, geom
FROM project.schools_staging

vacuum analyze project.schools

-- INSERT METRO STATIONS INTO DATABASE

CREATE TABLE project.metro_stations
(
	gid integer NOT NULL,
	name character varying(120),
	geom geometry(point, 3763)
);

CREATE INDEX ix_metro_stations
	ON project.metro_stations USING gist(geom)

-- NOT A SQL SCRIPT, SO IT'S GOING TO BE COMMENTED
-- IMPORT SHAPEFILES
-- shp2pgsql -D -s 3763 -g geom -I ./POIEducacao/POIEducacao.shp project.schools_staging | psql -h localhost -U postgres -p 5432 -d webmapping

INSERT INTO project.metro_stations (gid, name, geom)
SELECT gid, nome, geom
FROM project.metro_stations_staging

vacuum analyze project.metro_stations