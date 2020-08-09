import yaml

from bot.database.storage import StickfixDB
from bot.database.users import StickfixUser

if __name__ == "__main__":
    db = StickfixDB("users")
    users = { }
    for usr_id in db.get_keys():
        user = db[usr_id]
        user_inst = StickfixUser(usr_id)
        user_inst.private_mode = user.private_mode
        user_inst.stickers = user.stickers
        user_inst._shuffle = user._shuffle
        users[usr_id] = user_inst
    with open("data/users.yaml", "w") as fp:
        yaml.dump(users, fp, yaml.Dumper)
