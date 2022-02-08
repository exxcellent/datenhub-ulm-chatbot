from tinydb import TinyDB, Query


def exists(user_id, db, feedback):
    return True if db.count(feedback.user_id == user_id) > 0 else False


class DatabaseRequest:

    def __init__(self, db_location):
        self.db = TinyDB(db_location)
        self.Feedback = Query()

    def save_feedback(self, user_id, valuation, comment):
        if not exists(user_id, self.db, self.Feedback):
            self.db.insert({"user_id": user_id, "valuation": valuation, "comment": comment})
        else:
            self.db.update({"valuation": valuation, "comment": comment}, self.Feedback.user_id == user_id)
