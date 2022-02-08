import requests
from datetime import datetime, timedelta
import pytz
from statistics import median
import numpy as np
import pandas as pd


def convert_to_utc(timestamp):
    local = pytz.timezone("Europe/Berlin")
    local_dt = local.localize(timestamp, is_dst=None)
    return local_dt.astimezone(pytz.utc)


def convert_to_utc_zulu_string(timestamp):
    return str(convert_to_utc(timestamp))[:-6].replace(' ', 'T') + "Z"


def str_timestamp_to_datetime(str_timestamp):
    try:
        return datetime.strptime(str_timestamp, "%Y-%m-%dT%H:%M:%S.%f")
    except ValueError:
        return datetime.strptime(str_timestamp, "%Y-%m-%dT%H:%M:%S")


def resample_hourly(data):
    data = data.set_index("timestamp").sort_index()
    data = data.resample("H").mean().round()
    data.dropna(inplace=True)
    return data


def get_data_from_datastore(self, days, resource_id, data_point_id):
    start_time = convert_to_utc_zulu_string(datetime.now() - timedelta(days=days))

    data_json = requests.get(
        self.ckan_api + f"datastore_search_sql?sql=SELECT {data_point_id}, timestamp FROM \"{resource_id}\" WHERE "
                        f"timestamp >= '{start_time}' ORDER BY timestamp ASC").json()["result"]["records"]

    data = {}
    for i in data_json:
        timestamp = convert_to_utc(str_timestamp_to_datetime(i["timestamp"]))
        data[timestamp] = i[data_point_id]

    data = resample_hourly(pd.DataFrame(data.items(), columns=["timestamp", "count"]))
    return data


class RestRequests:

    def __init__(self, swagger_api, ckan_api):
        self.swagger_api = swagger_api
        self.ckan_api = ckan_api

    def get_categories(self):
        abbrev_categories = requests.get(self.ckan_api + "group_list").json()["result"]

        categories_dict = {}
        for i in abbrev_categories:
            result = requests.get(self.ckan_api + "group_show?id=" + i).json()["result"]
            if result["package_count"] != 0:
                categories_dict[i] = result["display_name"]

        return categories_dict

    def get_dataset_by_category(self, category_index):
        datasets_json = requests.get(self.ckan_api + "group_package_show?id=" + category_index).json()[
            "result"]
        datasets = {}
        for i in datasets_json:
            datasets[i["name"]] = i["title"]

        return datasets

    def get_description_of_dataset(self, selected_dataset):
        return requests.get(self.ckan_api + "package_show?id=" + selected_dataset).json()["result"]["notes"]

    def get_all_tags(self):
        tags_json = requests.get(self.ckan_api + "tag_list?all_fields=true").json()["result"]
        tags = {}
        for i in tags_json:
            tags[i["name"]] = i["display_name"]

        return tags

    def get_datasets_by_tag(self, tag_name):
        datasets_json = requests.get(self.ckan_api + "package_search?fq=tags:" + tag_name).json()["result"]["results"]
        datasets = {}
        for i in datasets_json:
            datasets[i["name"]] = i["title"]

        return datasets

    def get_news(self, days):
        number_of_all_datasets = str(len(requests.get(self.swagger_api + "datasets").json()))

        all_datasets = \
            requests.get(self.ckan_api + "package_search?&rows=" + number_of_all_datasets).json()["result"]["results"]

        time_format = "%Y-%m-%dT%H:%M:%S.%f"
        new_datasets = {}
        modified_datasets = {}
        time_now = datetime.now()

        for i in all_datasets:
            if datetime.strptime(i["metadata_created"], time_format) > time_now - timedelta(days=days):
                new_datasets[i["name"]] = i["title"]

            if datetime.strptime(i["metadata_modified"], time_format) > time_now - timedelta(days=days):
                modified_datasets[i["name"]] = i["title"]

        return new_datasets, modified_datasets

    # lorapark_hochwassersensor
    def get_water_level_danube_meters(self):

        water_level = requests.get(
            self.swagger_api + "datasets/lorapark_hochwassersensor/resources/LoRaPark_Hochwassersensor?limit=1&offset"
                               "=0&where=distance is not NULL ORDER BY timestamp DESC").json()["records"][0]["distance"]

        return float(water_level) / 1000

    def is_bike_path_flooded(self):

        four_hours_ago = datetime.now() - timedelta(hours=4)

        # REST API transfers timestamps in Zulu time, which means that summer and winter time is not congruent with CET
        four_hours_ago_utc = convert_to_utc(four_hours_ago)

        water_level_4h_list = requests.get(
            self.swagger_api + "datasets/lorapark_hochwassersensor/resources/LoRaPark_Hochwassersensor?where="
                               f"timestamp >='{convert_to_utc_zulu_string(four_hours_ago)}' ORDER BY timestamp DESC").json()[
            "records"]

        water_level_last_2_hours = np.array([])
        water_level_last_4_to_2_hours = np.array([])
        two_hours_ago = four_hours_ago_utc + timedelta(hours=2)

        for i in water_level_4h_list:

            timestamp = datetime.strptime(i["timestamp"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=pytz.utc)
            if two_hours_ago <= timestamp:
                water_level_last_2_hours = np.append(water_level_last_2_hours, i["distance"])
            else:
                water_level_last_4_to_2_hours = np.append(water_level_last_4_to_2_hours, i["distance"])

        return True if median(water_level_last_4_to_2_hours) - median(water_level_last_2_hours) >= 1000 else False

    def get_current_visitors_downtown_ulm(self):
        return int(requests.get(
            self.swagger_api + "datasets/besuchertrend-ulmer-innenstadt/resources/besuchertrend-ulmer-innenstadt"
                               "?limit=1&where=wifi is not NULL ORDER BY timestamp DESC").json()["records"][0]["wifi"])

    # statistical methods
    def get_data_besuchertrend_ulmer_innenstadt(self, days):
        return get_data_from_datastore(self, days, "6952f5ee-fd26-43fe-86c8-a73e5b0114d1", "wifi")

    def get_data_lorapark_besucherstrommessung(self, days):
        return get_data_from_datastore(self, days, "f4f347f0-db5d-4f6d-b043-6a841b7bb216", "wifi")

    def get_data_lorapark_hochwassersensor(self, days):
        data_mm = get_data_from_datastore(self, days, "eb1aaef3-bbe7-4f1a-a458-1b2044b1347f", "distance")
        return data_mm.div(1000)
