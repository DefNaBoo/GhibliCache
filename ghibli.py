#!/usr/bin/python
# -*- coding: utf-8 -*-

###############################################################################
#                          Ghibli Caching Exercice                            #
#                                                                             #
#                                                                             #
# author: Nabil CHAOURAR <nchaourar@nfox.fr>               Date: 25/08/2020   #
###############################################################################


from contextlib import contextmanager
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from threading import Event, Thread, Condition, Lock
from datetime import datetime
from urllib.request import urlopen as http_open
import json
from unittest import TestCase
from unittest.mock import Mock
import time

def get_uuid_from_url(url):
    uuid = url.split('/')[-1]
    return uuid

###############################################################################
#                                    Models                                   #
###############################################################################

# Here we are defining the models for the REST API

class Film:

    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.title = kwargs.get('title')
        self.director = kwargs.get('director')
        self.producer = kwargs.get('producer')
        self.release_date = kwargs.get('release_date')
        self.rt_score = kwargs.get('rt_score')
        self.characters = []
        self.species = []
        self.locations = []
        self.vehicles = []

class Species:

    def __init__(self,
                 films_collection=None,
                 **kwargs):
        self.id = kwargs.get('id')
        self.name = kwargs.get('name')
        self.classification = kwargs.get('classification')
        self.eye_color = kwargs.get('eye_color')
        self.hair_color = kwargs.get('hair_color')

        self.films = []
        # If we inject a film collections to the constructor we are able
        # to build relationship with the films
        if films_collection:
            for url in kwargs.get('films', []):
                uuid = get_uuid_from_url(url)
                film = films_collection.get(uuid)
                if film:
                    self.films.append(film)
                    film.species.append(self)

        self.people = []

class People:

    def __init__(self,
                 films_collection=None,
                 species_collection=None,
                 **kwargs):
        self.id = kwargs.get('id')
        self.name = kwargs.get('name')
        self.gender = kwargs.get('gender')
        self.age = kwargs.get('age')
        self.eye_color = kwargs.get('eye_color')
        self.hair_color = kwargs.get('hair_color')

        self.films = []
        # Same here ( see Species )
        if films_collection:
            for url in kwargs.get('films', []):
                uuid = get_uuid_from_url(url)
                film = films_collection.get(uuid)
                if film:
                    self.films.append(film)
                    film.characters.append(self)

        self.species = None
        # Same for species here
        if species_collection:
            url = kwargs.get('species')
            if url:
                uuid = get_uuid_from_url(url)
                species = species_collection.get(uuid)
                if species:
                    self.species = species
                    species.people.append(self)

        self.locations = []
        self.vehicles = []

class Location:

    def __init__(self,
                 films_collection=None,
                 people_collection=None,
                 **kwargs):
        self.id = kwargs.get('id')
        self.name = kwargs.get('name')
        self.climate = kwargs.get('climate')
        self.terrain = kwargs.get('terrain')
        self.surface_water = kwargs.get('surface_water')

        self.films = []
        # Same here ( see Species )
        if films_collection:
            for url in kwargs.get('films', []):
                uuid = get_uuid_from_url(url)
                film = films_collection.get(uuid)
                if film:
                    self.films.append(film)
                    film.locations.append(self)

        self.residents = []
        # Same for people
        if people_collection:
            for url in kwargs.get('people', []):
                uuid = get_uuid_from_url(url)
                resident = people_collection.get(uuid)
                if resident:
                    self.residents.append(resident)
                    resident.locations.append(self)


class Vehicle:

    def __init__(self,
                 films_collection=None,
                 people_collection=None,
                 **kwargs):
        self.id = kwargs.get('id')
        self.name = kwargs.get('name')
        self.description = kwargs.get('classification')
        self.vehicle_class = kwargs.get('eye_color')
        self.lenght = kwargs.get('hair_color')

        self.films = []
        # Same here ( see Species )
        if films_collection:
            for url in kwargs.get('films', []):
                uuid = get_uuid_from_url(url)
                film = films_collection.get(uuid)
                if film:
                    self.films.append(film)
                    film.vehicles.append(self)

        self.pilot = None
        # Same here for poeple
        if people_collection:
            url = kwargs.get('people')
            if url:
                uuid = get_uuid_from_url(url)
                pilot = people_collection.get(uuid)
                if pilot:
                    self.pilot = pilot
                    pilot.vehicles.append(self)

###############################################################################
#                          Server related stuff                               #
###############################################################################


class RWLock(object):
    """
        This class allows simutaneous read but only one write
    """

    def __init__(self):
        self._read_lock = Condition(Lock())
        self._readers_count = 0
        self._writers_count = 0

    def acquire_read(self):
        self._read_lock.acquire()
        if self._writers_count > 0:
            self._read_lock.wait_for(lambda: self._writers_count == 0)
        self._readers_count += 1
        self._read_lock.release()

    def release_read(self):
        self._read_lock.acquire()
        self._readers_count -= 1
        if self._readers_count == 0:
            self._read_lock.notify_all()
        self._read_lock.release()

    @contextmanager
    def acquire_reading(self):
        """ This method is here to be used via the `with` statement. """
        try:
            self.acquire_read()
            yield
        finally:
            self.release_read()

    def acquire_write(self):
        self._read_lock.acquire()
        self._writers_count += 1
        if self._readers_count > 0:
            self._read_lock.wait_for(lambda: self._readers_count == 0)

    def release_write(self):
        self._writers_count -= 1
        self._read_lock.notify_all()
        self._read_lock.release()

    @contextmanager
    def acquire_writing(self):
        """ This method is here to be used via the `with` statement. """
        try:
            self.acquire_write()
            yield
        finally:
            self.release_write()


class GhibliCache(object):
    """
        This class gather the data from the Ghibli API and hold it for us
    """
    raw_data = {'films': None,
                'people': None,
                'locations': None,
                'species': None,
                'vehicles': None}
    data = {'films': None,
            'people': None,
            'locations': None,
            'species': None,
            'vehicles': None}
    _cache_date = None
    _lock = RWLock()

    def __check_data(self):
        now = datetime.now()
        if self._cache_date is None or (now - self._cache_date).seconds > 60:
            self.update_data()

    def update_data(self):
        print("Updating data :")
        self.__gather_data_from_ghibli_server()
        # Here we are only locking the parsing because it's the part
        # that actually write the data we use plus accessing the
        # Ghibli API is really slow so we don't want to lock our
        # server for nothing
        with self._lock.acquire_writing():
            self.__parse_raw_data()
        self._cache_date = datetime.now()

    def __gather_data_from_ghibli_server(self):
        with http_open('https://ghibliapi.herokuapp.com/films') as res:
            self.raw_data['films'] = json.loads(res.read())
        with http_open('https://ghibliapi.herokuapp.com/people') as res:
            self.raw_data['people'] = json.loads(res.read())
        with http_open('https://ghibliapi.herokuapp.com/locations') as res:
            self.raw_data['locations'] = json.loads(res.read())
        with http_open('https://ghibliapi.herokuapp.com/species') as res:
            self.raw_data['species'] = json.loads(res.read())
        with http_open('https://ghibliapi.herokuapp.com/vehicles') as res:
            self.raw_data['vehicles'] = json.loads(res.read())

        print("done __gather_data_from_ghibli_server")

    def __parse_raw_data(self):
        films = {film['id']: Film(**film) for film in self.raw_data['films']}
        self.data['films'] = films
        species = {spec['id']: Species(films, **spec)
                   for spec in self.raw_data['species']}
        self.data['species'] = species
        people = {people['id']: People(films, species, **people)
                  for people in self.raw_data['people']}
        self.data['people'] = people
        locations = {loc['id']: Location(films, people, **loc)
                     for loc in self.raw_data['locations']}
        self.data['locations'] = locations
        vehicles = {vehi['id']: Vehicle(films, people, **vehi)
                    for vehi in self.raw_data['vehicles']}
        self.data['vehicles'] = vehicles

        print("done __parse_raw_data")

    def films(self):
        # First we check if our data is 'fresh' enough
        self.__check_data()
        films = None
        # Now we lock the data for reading
        with self._lock.acquire_reading():
            films = self.data['films'].values()
        return films


class GhibliCacheTimer(Thread):
    """
        This class is used to call the update_data method from the cache
    """

    def __init__(self, cache, event, wait_time=30):
        Thread.__init__(self)
        self.cache = cache
        self.stop_flag = event
        self.wait_time = wait_time

    def run(self):
        self.cache.update_data()
        while not self.stop_flag.wait(self.wait_time):
            self.cache.update_data()


class GhibliHandler(BaseHTTPRequestHandler):
    #  /!\ DON'T FORGET TO INJECT THE CACHE HERE /!\
    _cache = None

    def do_GET(self):
        """Respond to a GET request."""
        # If the path is correct
        if self._cache and self.path == '/movies/':
            films = self._cache.films()
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            content = "<html><head><title>List of Ghibli's movies</title>"
            content += "<body><table><thead><tr>"
            content += "<th>Movie</th><th>People in the movie</th>"
            content += "</tr></thead><tbody>"
            for film in films:
                people_list = ["{}({})".format(people.name,
                                               people.species.name)
                               for people in film.characters]
                content += "<tr><td>{}</td><td>{}</td></tr>".format(
                    film.title,
                    ', '.join(people_list))
            content += "</tbody></table></body></html"
            self.wfile.write(content.encode())
        else:
            self.send_response(404)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html>"
                             b"<head><title>404 Not found</title></head>"
                             b"</html>")

###############################################################################
#                                   Tests                                     #
###############################################################################


class GhibliCacheTimerTest(TestCase):

    def test_call(self):
        """
            Test if we call the update_data from the cache object at least once
        """
        cache_mock = Mock()
        stop_flag = Event()
        update_timer = GhibliCacheTimer(cache_mock, stop_flag, 0.1)
        update_timer.start()
        time.sleep(0.2)
        stop_flag.set()
        cache_mock.update_data.assert_called()

    def test_stop(self):
        """
            Test if stop_flag is working here we only want one call from the
            timer
        """
        cache_mock = Mock()
        stop_flag = Event()
        update_timer = GhibliCacheTimer(cache_mock, stop_flag, 0.3)
        update_timer.start()
        time.sleep(0.1)
        stop_flag.set()
        cache_mock.update_data.assert_called_once()


###############################################################################
#                                   Main                                      #
###############################################################################

if __name__ == '__main__':
    # Create the cache and the timer to update it
    cache = GhibliCache()
    stop_flag = Event()
    update_timer = GhibliCacheTimer(cache, stop_flag)
    update_timer.start()
    # Now let's create the http server
    print("Starting server :")
    GhibliHandler._cache = cache
    httpd = ThreadingHTTPServer(('127.0.0.1', 8080), GhibliHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        stop_flag.set()
    httpd.server_close()

# I think I have already pass too much time on it :) ( 8 hours )
# There are some things that could be better, the first one is
# to create some file to split differents parts here.
# I have write all class in only one file in order to be easier
# for you to read.
# I also used the standard library stuff to be "dependency-free".
# The HttpServer class by example is neither efficient nor safe here,
# if it was for a real application I would use Flask here. As there is
# no need to use the complete Django package.
# The test coverage is really poor, each element should be unit-
# tested.
# 
# I hope that you will enjoy the code review :)
