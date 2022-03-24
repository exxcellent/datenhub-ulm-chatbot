import io
import base64
import requests
import matrixprofile as mp
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

COLOR = "#674ea7"
DATE_FORMAT = "%d.%m.%Y"

"""
    Enkodiert gesetzte Plots in base64 
"""
def encode_plot():
    io_bytes = io.BytesIO()
    plt.savefig(io_bytes, format="png")
    io_bytes.seek(0)
    base64_boxplot = base64.b64encode(io_bytes.read())

    return str(base64_boxplot)[2:-1]

"""
    Berechnet Durchschnitt, Median sowie Standardabweichung der Daten
"""
def calculate_standard_methods(data):
    return [data.mean().round(1)["count"], data.median().round(1)["count"], data.std().round(1)["count"]]

"""
    Erstellt aus den Daten ein Boxplot
"""
def create_boxplot(data, x_label):
    fig, ax = plt.subplots()

    ax.set_title("Boxplot", fontsize=22)
    ax.boxplot(data, showfliers=False, vert=False, patch_artist=True, boxprops=dict(facecolor=COLOR))
    ax.set_yticks([])
    plt.xlabel(x_label, fontsize=18)

    return encode_plot()

"""
    Erstellt aus den Daten ein Liniendiagramm
"""
def create_line_diagram(data, y_label):
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.plot(data.index.values, data, color=COLOR)
    ax.xaxis.set_major_formatter(mdates.DateFormatter(DATE_FORMAT))
    fig.autofmt_xdate()
    plt.title("Liniendiagramm", fontsize=22)
    plt.ylabel(y_label, fontsize=18)
    plt.xlabel("Datum", fontsize=18)

    return encode_plot()

"""
    Erstellt aus den Daten ein Plot zur Anomalienanalyse nach Matrix Profile
"""
def create_discord_plot(data):
    profile = mp.compute(data['count'].values, 8)  # 8 hour profile

    profile = mp.discover.discords(profile, k=3)  # top 3 discords
    window_size = profile['w']
    mp_adjusted = np.append(profile['mp'], np.zeros(window_size - 1) + np.nan)

    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.plot(data.index.values, mp_adjusted, color=COLOR)
    ax.xaxis.set_major_formatter(mdates.DateFormatter(DATE_FORMAT))
    fig.autofmt_xdate()
    plt.title("Top 3 Anomalien (rot)", fontsize=22)
    plt.xlabel("Datum", fontsize=18)

    for start_index in profile['discords']:
        x = data.index.values[start_index:start_index + window_size]
        y = mp_adjusted[start_index:start_index + window_size]
        plt.plot(x, y, c='r')

    return encode_plot()

"""
    Lädt die base64 plots zum Image Provider Service hoch, via REST API
"""
def upload_pictures(self, images_byte64):
    image_uris = []
    for i in images_byte64:
        session = requests.Session()
        payload = {"key": self.api_key, "image": i}
        image_uris.append(session.post(self.picture_service, data=payload).json()["data"]["url"])
    return image_uris


class StatisticalCalculations:

    def __init__(self, picture_service, api_key):
        self.picture_service = picture_service
        self.api_key = api_key

    def calculate_besuchertrend_ulmer_innenstadt(self, data):
        images_byte64 = [create_boxplot(data, "Anzahl Personen"),
                         create_line_diagram(data, "Besucher"),
                         create_discord_plot(data)]
        image_uris = upload_pictures(self, images_byte64)
        return calculate_standard_methods(data), image_uris

    def calculate_lorapark_besucherstrommessung(self, data):
        images_byte64 = [create_boxplot(data, "Anzahl Personen"),
                         create_line_diagram(data, "Besucher"),
                         create_discord_plot(data)]
        image_uris = upload_pictures(self, images_byte64)
        return calculate_standard_methods(data), image_uris

    def calculate_lorapark_hochwassersensor(self, data):
        images_byte64 = [create_boxplot(data, "Wasserlevel in Meter"),
                         create_line_diagram(data, "Höhe in Meter"),
                         create_discord_plot(data)]
        image_uris = upload_pictures(self, images_byte64)
        return calculate_standard_methods(data), image_uris
