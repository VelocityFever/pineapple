import requests
import urllib.request
import os
from util import Events
import sqlite3
import traceback
import operator
import discord
from PIL import Image

class Plugin(object):
    def __init__(self, pm):
        self.pm = pm
        self.api_key = self.pm.botPreferences.get_config_value("OSU", "apikey")
        # base_url controls parameters for lammmy generation. Use python string format to change mode/username
        self.base_url = "http://lemmmy.pw/osusig/sig.php?mode={}&pp=0&removemargin&darktriangles&colour=pink&uname={}"

    @staticmethod
    def register_events():
        return [Events.Command("osu", desc="Get the osu!standard details for a user"),
                Events.Command("ctb", desc="Get the osu!catch the beat details for a user"),
                Events.Command("taiko", desc="Get the osu!taiko details for a user"),
                Events.Command("mania", desc="Get the osu!mania details for a user"),
                Events.Command("leaderboard", desc="Get the server leaderboard for a mode (osu, ctb, taiko, mania)"),
                Events.Command("setosu", desc="Register your osu! username to your discord account. "
                                              "Will add you to the leaderboards"),
                Events.Command("deleteosu", desc="Staff command to remove a user from the leaderboard")]

    async def handle_command(self, message_object, command, args):
        if command == "osu":
            await self.osu_mode(message_object, args[1].strip(), 0)
        if command == "ctb":
            await self.osu_mode(message_object, args[1].strip(), 2)
        if command == "taiko":
            await self.osu_mode(message_object, args[1].strip(), 1)
        if command == "mania":
            await self.osu_mode(message_object, args[1].strip(), 3)
        if command == "leaderboard":
            await self.leaderboard(message_object, args[1].strip())
        if command == "setosu":
            await self.set_osu(message_object, args[1])
        if command == "deleteosu":
            id = message_object.mentions[0].id
            await self.delete_osu(id)

    async def osu_mode(self, message_object, username, mode):
        try:
            if len(username) is 0 or username is None:
                username = await self.get_osu_name(message_object)
                if username is None:
                    return
            await self.get_badge(message_object.channel, username, mode)
            # display_data = await self.get_data(username, mode)
            # await self.pm.client.send_message(message_object.channel,
            #                                  "Username: " + display_data["username"] + "\n" + "Rank: " + display_data[
            #                                      "pp_rank"] + "\n" + "Accuracy: " + display_data[
            #                                      "accuracy"] + "\n" + "PP: " + display_data[
            #                                      "pp_raw"] + "\n" + "Country: " + display_data[
            #                                      "country"] + "\n" + "Rank in country: " + display_data[
            #                                      "pp_country_rank"])
        except:
            await self.pm.client.send_message(message_object.channel, "Error unknown user **" + username + "**")

    async def get_badge(self, channel, username, id):
        directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
        if not os.path.exists(directory):
            os.makedirs(directory)
        filename = os.path.join(directory, username + "test.jpg")
        image_url = self.base_url.format(id, username)
        urllib.request.urlretrieve(image_url, filename)

        # Check if image is valid
        try:
            im = Image.open(filename)
            im.close()
            await self.pm.client.send_file(channel, filename)
        except IOError:
            await self.pm.client.send_message(channel, "No stats found for this gamemode.")
        os.remove(filename)

    async def get_data(self, username, id):
        api_key = self.api_key
        url = 'https://osu.ppy.sh/api/get_user?m=' + str(id) + '&k=' + api_key + '&u=' + username
        response = requests.get(url, verify=True)
        return response.json()[0]

    async def leaderboard(self, message_object, mode):
        if not os.path.exists("cache/"):
            os.makedirs("cache")
        if mode is "":
            await self.pm.client.send_message(message_object.channel,
                                              "Please specify the gamemode (osu, taiko, ctb, mania)")
            return
        try:
            lb_msg = await self.pm.client.send_message(message_object.channel, "Loading leaderboard...")
            if mode == "osu":
                id = 0
            elif mode == "taiko":
                id = 1
            elif mode == "ctb":
                id = 2
            elif mode == "mania":
                id = 3
            else:
                mode = "osu"
                id = 0
            con = sqlite3.connect("cache/osu_leaderboard.sqlite",
                                  detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
            with con:
                cur = con.cursor()
                cur.execute("SELECT * FROM users")  # TODO: Improve loading to show more users
                rows = cur.fetchall()
                index = 1
                msg = "Leaderboard for " + mode + ":\n"
                unsorted = list()

                for row in rows:
                    try:
                        data = await self.get_data(row[1], id)
                        if data["pp_rank"] != "0":
                            data["discord_id"] = row[0]
                            data["pp_rank"] = int(data["pp_rank"])
                            unsorted.append(data)
                    except:
                        continue

                sortedusers = sorted(unsorted, key=operator.itemgetter("pp_rank"))
                for data in sortedusers:
                    try:
                        user = await self.pm.client.get_user_info(data["discord_id"])
                        member = discord.utils.find(lambda m: m.name == user.name,
                                                    message_object.channel.server.members)
                        if member is None:
                            await self.delete_osu(data["discord_id"])
                            continue

                        # fetch correct display name
                        if hasattr(user, 'nick') and user.nick != "":
                            name = user.nick
                        else:
                            name = user.name

                        # get an emoji for top 3
                        emoji = ""
                        if index is 1:
                            emoji = ":first_place:"
                        elif index is 2:
                            emoji = ":second_place:"
                        elif index is 3:
                            emoji = ":third_place:"
                        else:
                            emoji = str(index) + "#:"

                        msg += emoji + " " + data["username"] + "  #" + str(data["pp_rank"]) + " (" + str(
                            int(float(data[
                                          "pp_raw"]))) + "pp)" + " (" + name + ") \n"
                        index += 1
                    except:
                        traceback.print_exc()
                await self.pm.client.delete_message(lb_msg)
                await self.pm.client.send_message(message_object.channel, msg)
        except:
            traceback.print_exc()

    async def set_osu(self, message_object, name):
        user_id = message_object.author.id
        if name is not "" and name is not None:
            if not os.path.exists("cache/"):
                os.makedirs("cache")
            try:
                con = sqlite3.connect("cache/osu_leaderboard.sqlite",
                                      detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
                with con:
                    cur = con.cursor()
                    cur.execute(
                        "CREATE TABLE IF NOT EXISTS users(Id TEXT PRIMARY KEY, Username TEXT)")
                    cur.execute(
                        'INSERT OR IGNORE INTO users(Id, Username) VALUES(?, ?)',
                        (str(user_id), name))

                    cur.execute("UPDATE users SET Username = ? WHERE Id = ?",
                                (name, str(user_id)))

                    await self.pm.client.send_message(message_object.channel,
                                                      message_object.author.mention +
                                                      " your osu! username has been set to **" + name + "**")
            except:
                traceback.print_exc()
        else:
            await self.delete_osu(user_id)

    async def delete_osu(self, id):
        if not os.path.exists("cache/"):
            os.makedirs("cache")
        try:
            con = sqlite3.connect("cache/osu_leaderboard.sqlite",
                                  detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
            with con:
                cur = con.cursor()
                cur.execute("DELETE FROM users WHERE Id=?", (id,))
        except:
            traceback.print_exc()

    async def get_osu_name(self, msg):
        con = sqlite3.connect("cache/osu_leaderboard.sqlite",
                              detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        with con:
            cur = con.cursor()
            cur.execute("SELECT Username FROM users WHERE Id = ?", (msg.author.id,))
            rows = cur.fetchall()

            for row in rows:
                    return row[0]

            await self.pm.client.send_message(msg.channel,
                                              "No username set for " + msg.author.mention +
                                              ". You can set one by using the `setosu <osu name>` command")
            return None

