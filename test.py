import yaml

from bot.database.storage import StickfixDB

if __name__ == "__main__":
    db = StickfixDB("stickfix-user-DB")
    users = { }
    for usr_id in db.get_keys():
        users[usr_id] = db.get_item(usr_id).to_dict()
    with open("data/users.yaml", "w") as fp:
        yaml.dump(users, fp, yaml.Dumper)
