#!/usr/bin/env python3

import sys
import csv
import requests
from SPARQLWrapper import SPARQLWrapper, JSON


organisations = {}
gss = {}

fields = [
    "organisation",
    "name",
    "website",
    "statistical-geography",
    "toid",
    "opendatacommunities",
    "data-govuk",
    "wikidata",
    "start-date",
    "end-date",
]


def load(f, key, fields, prefix=""):
    for row in csv.DictReader(f):
        if row[key]:
            curie = prefix + row[key]
            organisations.setdefault(curie, {})
            for field in fields:
                to = (
                    "statistical-geography"
                    if field.startswith("statistical-geography")
                    else field
                )
                if row[field]:
                    organisations[curie][to] = row[field]


def load_register(key, fields, register=None):
    url = "https://%s.register.gov.uk/records.csv?page-index=1&page-size=5000" % (
        register or key
    )
    return load(
        requests.get(url).content.decode("utf-8").splitlines(),
        key,
        fields,
        prefix=key + ":",
    )


def load_file(path, key, fields):
    return load(open(path), key, fields)


def index(key):
    index = {}
    for o in organisations:
        if key in organisations[o]:
            index[organisations[o][key]] = o
    return index


def remove_prefix(value, prefix):
    if prefix and value.startswith(prefix):
       return value[len(prefix):]
    return value


def patch(results, key, fields, col=None, prefix=None):
    if not col:
        col = key
    keys = index(key)
    for d in results["results"]["bindings"]:
        row = {}
        for k in d:
            row[k] = d[k]["value"]

        if col in row and row[col] in keys:
            organisation = keys[row[col]]
            for field in fields:
                value = remove_prefix(row[field], prefix)
                organisations[organisation].setdefault(field, value)


def patch_sparql(endpoint, query, key, fields, col=None, prefix=None):
    sparql = SPARQLWrapper(
        endpoint,
        agent="Mozilla/5.0 (Windows NT 5.1; rv:36.0) Gecko/20100101 Firefox/36.0",
    )

    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    patch(sparql.query().convert(), key, fields, col, prefix)


load_register("local-authority-eng", ["name", "official-name", "end-date"])
load_register("government-organisation", ["name", "website", "end-date"])

# statistical geography codes
load_register(
    "local-authority-eng",
    ["statistical-geography-county-eng"],
    register="statistical-geography-county-eng",
)
load_register(
    "local-authority-eng",
    ["statistical-geography-london-borough-eng"],
    register="statistical-geography-london-borough-eng",
)
load_register(
    "local-authority-eng",
    ["statistical-geography-metropolitan-district-eng"],
    register="statistical-geography-metropolitan-district-eng",
)
load_register(
    "local-authority-eng",
    ["statistical-geography-non-metropolitan-district-eng"],
    register="statistical-geography-non-metropolitan-district-eng",
)
load_register(
    "local-authority-eng",
    ["statistical-geography-unitary-authority-eng"],
    register="statistical-geography-unitary-authority-eng",
)

# assert fixes
load_file(
    "data/organisation.csv",
    "organisation",
    ["name", "website", "statistical-geography"],
)

# add development corporation names and URIs from opencommunities.org
patch_sparql(
    "https://opendatacommunities.org/sparql",
    """
    PREFIX admingeo: <http://opendatacommunities.org/def/ontology/admingeo/>
    PREFIX localgov: <http://opendatacommunities.org/def/local-government/>
    SELECT DISTINCT ?opendatacommunities ?name ?gss
    WHERE {
        VALUES ?o {
            admingeo:nationalPark
            admingeo:County
            admingeo:UnitaryAuthority
            admingeo:MetropolitanDistrict
            admingeo:NonMetropolitanDistrict
            admingeo:LondonBorough
            localgov:DevelopmentCorporation
        }
        ?opendatacommunities ?p ?o ;
            <http://publishmydata.com/def/ontology/foi/displayName> ?name ;
            <http://publishmydata.com/def/ontology/foi/code> ?gss
    }
    """,
    "statistical-geography",
    ["name", "opendatacommunities"],
    "gss",
)


# add website, toids from wikidata
patch_sparql(
    "https://query.wikidata.org/sparql",
    """
    SELECT DISTINCT ?wikidata ?gss ?toid ?website
    WHERE
    {
      VALUES ?q {
        wd:Q1187580
        wd:Q1006876
        wd:Q1002812
      }
      ?wikidata wdt:P31 wd:Q1006876;
             wdt:P3120 ?toid;
             wdt:P856 ?website;
             OPTIONAL { ?wikidata wdt:P836 ?gss }
    }
    """,
    "statistical-geography",
    ["wikidata", "website", "toid"],
    "gss",
    prefix="http://www.wikidata.org/entity/",
)


w = csv.DictWriter(sys.stdout, fields, extrasaction="ignore")
w.writeheader()
for organisation in sorted(organisations):
    o = organisations[organisation]
    o["organisation"] = organisation
    o["name"] = o.get("official-name", o.get("name", ""))
    w.writerow(o)
