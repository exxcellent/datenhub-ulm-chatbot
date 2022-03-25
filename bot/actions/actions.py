import random
from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict
from rasa_sdk.events import FollowupAction

from .rest import RestRequests
from .database_connection import DatabaseRequest
from .statistical_calculations import StatisticalCalculations

rest = RestRequests("https://datenhub.ulm.de/api/v1/", "https://datenhub.ulm.de/ckan/api/3/action/")
db = DatabaseRequest("feedback.json")
calc = StatisticalCalculations("https://api.imgbb.com/1/upload", "")  # todo: add valid imgbb api key

"""
    Custom action SaveFeedbackAction:
    Persistiert Feedback des Nutzers. Die Daten werden direkt aus dem Tracker abgerufen.
"""
class SaveFeedbackAction(Action):

    def name(self) -> Text:
        return "save_feedback_form"

    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[
        Dict[Text, Any]]:
        db.save_feedback(tracker.sender_id, int(tracker.get_slot("feedback_valuation")),
                         str(tracker.get_slot("feedback_comment")))

        return [SlotSet("feedback_valuation", None), SlotSet("feedback_comment", None)]

"""
    Form validator ValidateFeedbackForm:
    Validiert nur die Feedback Zahl zwischen 1 und 10. 1 >= x <= 10
    Kann um die Methode für das Kommentarfeld erweitert werden
"""
class ValidateFeedbackForm(FormValidationAction):

    def name(self) -> Text:
        return "validate_feedback_form"

    def validate_feedback_valuation(self,
                                    slot_value: Any,
                                    dispatcher: "CollectingDispatcher",
                                    tracker: "Tracker",
                                    domain: "DomainDict",
                                    ) -> Dict[Text, Any]:
        try:
            valuation = int(slot_value)
            if 1 <= valuation <= 10:
                dispatcher.utter_message(text="Vielen Dank. Bitte schreibe uns, was dir auf dem Herzen liegt. "
                                              "Ein kurzer Kommentar reicht dabei schon aus.")
                return {"feedback_valuation": valuation}
            else:
                dispatcher.utter_message(text="Diese Bewertung liegt nicht zwischen 1 und 10.")
                return {"feedback_valuation": None}
        except ValueError:
            dispatcher.utter_message(text="Diese Angabe ist keine Zahl. Bitte nenne eine Zahl zwischen 1 und 10.")
            return {"feedback_valuation": None}

"""
    Custom action YesHelpAction:
    Folgt auf den Button "Yes" nach Hilfe action
    Zeigt alle verfügbaren Kategorien in Form einer buttons list an. 
"""
class YesHelpAction(Action):

    def name(self) -> Text:
        return "show_categories_action"

    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[
        Dict[Text, Any]]:
        categories_dict = rest.get_categories()
        buttons = []
        for i in categories_dict:
            buttons.append({"payload": f'/display_dataset_by_category{{"selected_category": "{i}"}}',
                            "title": categories_dict[i]})

        dispatcher.utter_message(text="Dies sind alle Kategorien, die ich im Angebot habe:", buttons=buttons)

        return []

"""
    Custom action DisplayDatasetByCategoryAction:
    Zeigt alle Datensätze die einer Kategorie zugewiesen wurden, in Form einer buttons list an.
"""
class DisplayDatasetByCategoryAction(Action):

    def name(self) -> Text:
        return "display_dataset_by_category_action"

    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[
        Dict[Text, Any]]:

        selected_category = str(tracker.get_slot("selected_category"))
        datasets_dict = rest.get_dataset_by_category(selected_category)

        if datasets_dict:
            buttons = []
            for i in datasets_dict:
                buttons.append({"payload": f'/display_dataset_description{{"selected_dataset": "{i}"}}',
                                "title": datasets_dict[i]})

            dispatcher.utter_message(text="Dies sind alle Datensätze der ausgewählten Kategorie:", buttons=buttons)
        else:
            dispatcher.utter_message(text="Zu dieser Kategorie gibt es noch keine Datensätze.")

        return []

"""
    Custom action DisplayDatasetDescriptionAction:
    Zeigt den beschreibenden Text eines Datensatzes an, welcher durch DisplayDatasetByCategoryAction ausgewählt wurde
"""
class DisplayDatasetDescriptionAction(Action):

    def name(self) -> Text:
        return "display_dataset_description_action"

    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[
        Dict[Text, Any]]:
        selected_dataset = str(tracker.get_slot("selected_dataset"))
        description = rest.get_description_of_dataset(selected_dataset)

        dispatcher.utter_message(text="Diese Informationen konnte ich diesbezüglich finden:")
        dispatcher.utter_message(text=f"\"{description}\"")
        dispatcher.utter_message(text="Mehr Informationen zu diesem Datensatz findest du [hier]"
                                      f"(https://datenhub.ulm.de/ckan/dataset/{selected_dataset})!")

        return []

"""
    Custom action ShowTagAction
    Ähnlich wie YesHelpAction, bloß für tags. Alphabetisch sortiert. Nur 10 tags werden angezeigt. Button "Mehr tags" zeigt 10 nächste Tags an
"""
class ShowTagAction(Action):

    def name(self) -> Text:
        return "show_tags_action"

    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[
        Dict[Text, Any]]:

        tags_iteration = int(tracker.get_slot("tags_iteration"))

        tags_dict = rest.get_all_tags()
        tags_dict = {k: tags_dict[k] for k in list(tags_dict)[tags_iteration:tags_iteration + 10]}

        if len(tags_dict) != 0:
            buttons = []
            for i in tags_dict:
                buttons.append({"payload": f'/display_dataset_by_tag{{"selected_tag": "{i}"}}',
                                "title": tags_dict[i]})
            buttons.append({"payload": "/show_more_tags", "title": "Mehr Tags"})

            dispatcher.utter_message(text="Hier sind 10 Tags:", buttons=buttons)
            return [SlotSet("tags_iteration", tags_iteration + 10)]
        else:
            dispatcher.utter_message(
                text="Mehr Tags gibt es leider nicht. Vielleicht findest du was du suchst, wenn du nach "
                     "Kategorien sortierst.")
            return [SlotSet("tags_iteration", 0)]

"""
    Custom action DisplayDatasetByTagAction:
    Zeigt alle Datensätze, die mit gewählten tag verknüpft sind
"""
class DisplayDatasetByTagAction(Action):

    def name(self) -> Text:
        return "display_dataset_by_tag_action"

    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[
        Dict[Text, Any]]:

        selected_tag = str(tracker.get_slot("selected_tag"))
        datasets_dict = rest.get_datasets_by_tag(selected_tag)

        if datasets_dict:
            buttons = []
            for i in datasets_dict:
                buttons.append({"payload": f'/display_dataset_description{{"selected_dataset": "{i}"}}',
                                "title": datasets_dict[i]})

            dispatcher.utter_message(text="Dies sind alle Datensätze des ausgewählten Tags:", buttons=buttons)
        else:
            dispatcher.utter_message(text="Zu diesem Tag gibt es noch keine Datensätze.")

        return [SlotSet("tags_iteration", 0)]

"""
    Methode:
    Baut den String für die News Action aus neuen und modifizierten Datensätzen
"""
def build_news_string(new_datasets, modified_datasets, checked_days):
    news_output = ""
    if len(new_datasets) != 0:
        news_output += f"**Folgende Datensätze wurden in den letzten {checked_days} Tagen hinzugefügt:**\r\n\r\n"
        for key, value in new_datasets.items():
            news_output += "\r\n* " + f"[{value}](https://datenhub.ulm.de/ckan/dataset/{key})"
        news_output += "\n\n"

    if len(modified_datasets) != 0:
        news_output += f"**Folgende Datensätze haben sich in den letzten {checked_days} Tagen verändert:**\r\n\r\n"
        for key, value in modified_datasets.items():
            news_output += "\r\n* " + f"[{value}](https://datenhub.ulm.de/ckan/dataset/{key})"

    return news_output

"""
    Custom action ShowNewsAction:
    Überprüft, welche Datensätze in den letzten 7 Tagen modifiert oder hinzugefügt wurden. Wenn == 0, werden auf Wunsch die letzten 30 Tage überprüft.
"""
class ShowNewsAction(Action):

    def name(self) -> Text:
        return "show_news_action"

    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[
        Dict[Text, Any]]:

        if not bool(tracker.get_slot("news_show_30_days")):
            new_datasets, modified_datasets = rest.get_news(7)

            if len(new_datasets) == 0 and len(modified_datasets) == 0:
                button = [{"payload": "/show_news_30", "title": "Schaue nach den letzten 30 Tagen"}]
                dispatcher.utter_message(text="In den letzten sieben Tagen gab es keine Veränderungen!", buttons=button)
                return [SlotSet("news_show_30_days", True)]

            dispatcher.utter_message(text=build_news_string(new_datasets, modified_datasets, "sieben"))

            return [SlotSet("news_show_30_days", False)]
        else:
            new_datasets, modified_datasets = rest.get_news(30)

            if len(new_datasets) == 0 and len(modified_datasets) == 0:
                dispatcher.utter_message(text="Auch in den letzten 30 Tagen gab es keine Veränderungen!")
                return [SlotSet("news_show_30_days", False)]

            dispatcher.utter_message(text=build_news_string(new_datasets, modified_datasets, "30"))

            return [SlotSet("news_show_30_days", False)]


# lorapark_hochwassersensor
"""
    Custom Action ShowCurrentWaterLevelDanubeAction:
    Gibt den aktuellen Wasserstand der Donau wieder.
"""
class ShowCurrentWaterLevelDanubeAction(Action):
    def name(self) -> Text:
        return "show_current_water_level_danube_action"

    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[
        Dict[Text, Any]]:
        water_level_danube_meters = str(rest.get_water_level_danube_meters()).replace(".", ",")
        dispatcher.utter_message(
            text=f"Der Wasserspiegel der Donau beträgt momentan {water_level_danube_meters} Meter.")

        return []

"""
    Custom action IsBikePathFloodedAction:
    Gibt wieder, ob der Fuß- und Fahrradweg überflutet ist (Rechnung erfolgt in rest Klasse)
"""
class IsBikePathFloodedAction(Action):
    def name(self) -> Text:
        return "is_bike_path_flooded_action"

    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[
        Dict[Text, Any]]:

        if rest.is_bike_path_flooded():
            text = "Die Donau hat momentan Hochwasser und der Fahrrad- sowie Fußgängerweg ist somit überflutet und " \
                   "nicht betretbar. "
        else:
            text = "Die Donau hat momentan kein Hochwasser und der Fahrrad- sowie Fußgängerweg ist nicht überflutet " \
                   "und somit betretbar. "

        dispatcher.utter_message(text=text)

        return []

"""
    Custom action ShowCurrentVisitorsDowntownUlmAction:
    Gibt die Anzahl an aktuellen Besuchern der Innenstadt wieder.
"""
class ShowCurrentVisitorsDowntownUlmAction(Action):

    def name(self) -> Text:
        return "show_current_visitors_downtown_ulm_action"

    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[
        Dict[Text, Any]]:
        current_visitors = rest.get_current_visitors_downtown_ulm()

        dispatcher.utter_message(
            text=f"In dieser Sekunde halten sich {current_visitors} Besucher in der Ulmer Innenstadt auf (geschätzter Wert).")

        return []

"""
    Custom action ShowRandomFact:
    Gibt random einen der folgenden drei custom actions wieder: ShowCurrentVisitorsDowntownUlmAction, IsBikePathFloodedAction und ShowCurrentWaterLevelDanubeAction
"""
class ShowRandomFact(Action):

    def name(self) -> Text:
        return "show_random_fact_action"

    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[
        Dict[Text, Any]]:
        available_actions = ["show_current_water_level_danube_action",
                             "is_bike_path_flooded_action",
                             "show_current_visitors_downtown_ulm_action"]

        return [FollowupAction(random.choice(available_actions))]


# Analytical Actions

# this list can not be pulled from the api as it is a set of chosen datasets. It has to be extended manually if new
# statistical methods will be added. Dict consist of: key: resource id; value: display name
def get_available_datasets():
    return {"6952f5ee-fd26-43fe-86c8-a73e5b0114d1": "Besuchertrend Ulmer Innenstadt",
            "f4f347f0-db5d-4f6d-b043-6a841b7bb216": "Besucherstrommessung im LoRaPark im Weinhof",
            "eb1aaef3-bbe7-4f1a-a458-1b2044b1347f": "Radweg-Hochwassersensor am Donauradweg sowie an der Blau"}


""" 
    These two entries will not be needed for now. Luftqualität Eselsberg has little to no available data. 
    With data from Fahrrad Dauerzählstelle you need to calculate the common air quality index first 
    -> not scope of thesis.
    {"b49de35e-040c-4530-9208-eefadc97b610": "Luftqualität Eselsberg",
    "49631b61-cda1-46af-b58c-f1e4965f0bd4": "Fahrrad-Dauerzählstelle am Blautalradweg"}
"""

"""
    Custom action CallForAnalyticalGraphAction:
    Gibt alle verfügbaren Datensätze wieder, welche für die analytischen Auswertungen verwendet werden können.
"""
class CallForAnalyticalGraphAction(Action):

    def name(self) -> Text:
        return "call_for_analytical_graph_action"

    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[
        Dict[Text, Any]]:
        available_datasets = get_available_datasets()

        buttons = []
        for key, value in available_datasets.items():
            buttons.append({"payload": f'/graph_ask_for_time_range{{"selected_dataset_for_graph": "{key}"}}',
                            "title": value})

        dispatcher.utter_message(text="Folgende Datensätze stehen zur Auswahl:", buttons=buttons)

        return []

"""
    Custom action GraphAskForTimeRange:
    Gibt voreingestellte Zeiträume wieder, für analytische Auswertungen.
"""
class GraphAskForTimeRange(Action):
    def name(self) -> Text:
        return "graph_ask_for_time_range_action"

    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[
        Dict[Text, Any]]:
        buttons = [{"payload": '/create_graphs{"selected_time_range_for_graph_days": "2"}', "title": "Letzte 2 Tage"},
                   {"payload": '/create_graphs{"selected_time_range_for_graph_days": "4"}', "title": "Letzte 4 Tage"},
                   {"payload": '/create_graphs{"selected_time_range_for_graph_days": "7"}', "title": "Letzte Woche"},
                   {"payload": '/create_graphs{"selected_time_range_for_graph_days": "14"}',
                    "title": "Letzte 2 Wochen"}]

        dispatcher.utter_message("Daten aus welchem Zeitraum sollen berücksichtigt werden?", buttons=buttons)
        return []

"""
    Custom action CreateGraphsAction:
    Ruft Funktionen der Klasse statistical_calculations auf, um Grafiken zu generieren.
    Am Ende werden die erstellten Grafiken sowie der beschreibende Text für die Standardberechnungen wiedergegeben
"""
class CreateGraphsAction(Action):
    def name(self) -> Text:
        return "create_graphs_action"

    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[
        Dict[Text, Any]]:

        dataset = tracker.get_slot("selected_dataset_for_graph")
        time_range = int(tracker.get_slot("selected_time_range_for_graph_days"))

        picture_links = None
        standard_methods = None
        unit = None
        if dataset == "6952f5ee-fd26-43fe-86c8-a73e5b0114d1":
            # Besuchertrend Ulmer Innenstadt
            data = rest.get_data_besuchertrend_ulmer_innenstadt(time_range)
            standard_methods, picture_links = calc.calculate_besuchertrend_ulmer_innenstadt(data)
            unit = "Besuchern"
        elif dataset == "f4f347f0-db5d-4f6d-b043-6a841b7bb216":
            # Besucherstrommessung im LoRaPark im Weinhof
            data = rest.get_data_lorapark_besucherstrommessung(time_range)
            standard_methods, picture_links = calc.calculate_lorapark_besucherstrommessung(data)
            unit = "Besuchern"
        elif dataset == "eb1aaef3-bbe7-4f1a-a458-1b2044b1347f":
            # Radweg-Hochwassersensor am Donauradweg sowie an der Blau
            data = rest.get_data_lorapark_hochwassersensor(time_range)
            standard_methods, picture_links = calc.calculate_lorapark_hochwassersensor(data)
            unit = "Metern"

        if picture_links is not None and standard_methods is not None and unit is not None:
            dispatcher.utter_message(
                text=f"Der ausgewählte Datensatz hat in den letzten {time_range} Tagen einen Durchschnitt von "
                     f"**{str(standard_methods[0]).replace('.', ',')} {unit}** erreicht. Dabei beträgt der Median "
                     f"einen Wert von "
                     f"**{str(standard_methods[1]).replace('.', ',')} {unit}**. Die Daten haben eine Standardabweichung"
                     f" von **{str(standard_methods[2]).replace('.', ',')} {unit}**.")

            for i in picture_links:
                dispatcher.utter_message(image=i)
        else:
            dispatcher.utter_message(text="Entschuldige, etwas scheint schiefgelaufen zu sein. Versuche es am besten "
                                          "einfach erneut.")

        return [SlotSet("selected_dataset_for_graph", None), SlotSet("selected_time_range_for_graph_days", None)]
# New action can simply be added by creating a class that inherits from Action
