""" "Stickfix" (c) by Ignacio Slater M.
    "Stickfix" is licensed under a
    Creative Commons Attribution 4.0 International License.

    You should have received a copy of the license along with this
    work. If not, see <http://creativecommons.org/licenses/by/4.0/>.
"""

import yaml

from bot.stickfix import Stickfix

if __name__ == "__main__":
    with open("secret.yml") as secret:
        data = yaml.load(secret, Loader=yaml.FullLoader)
        token = data["token"]["test"]
        admins = data["admins"]
        Stickfix(token).run()
