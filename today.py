import os
import json
import hashlib
import requests
from lxml import etree
from pprint import pprint
from dotenv import load_dotenv

from datetime import datetime as dt
from dateutil import relativedelta

load_dotenv()


class Stats:
    def __init__(self) -> None:
        self.token = os.environ["ACCESS_TOKEN"]
        self.headers = {"authorization": "token " + self.token}
        self.user_id = self.get_viewer_id()
        self.cache_filename = "cache.json"
        self.username = "salko-ua"

        # MAIN
        self.os = "Linux (NixOS 25.05)"
        self.birthday = dt(2006, 3, 27)
        self.host = "Ukraine"
        self.kernel = "Volyn, Lutsk"
        self.ide = "Lazy Nvim v0.11.2"

        # STACK
        self.programming = "Python, JavaScript, VBA, SQL"
        self.frontend = "Svelte, Tailwind CSS"
        self.backend = "FastAPI, SQLAlchemy, Docker"
        self.database = "PostgreSQL, MONGODB, SQLite, Redis"
        self.other = "HTML, CSS, JSON, MARKDOWN"

        self.scope = ["OWNER", "COLLABORATOR", "ORGANIZATION_MEMBER"]

    def get_viewer_id(self) -> str:
        query = """
        query {
            viewer {
                id
            }
        }
        """
        response = requests.post(
            "https://api.github.com/graphql",
            json={"query": query},
            headers=self.headers,
        )
        return response.json()["data"]["viewer"]["id"]

    def get_age(self) -> str:
        """
        Returns the length of time since I was born e.g.
        >>> 'XX years, XX months, XX days'
        """
        diff = relativedelta.relativedelta(dt.today(), self.birthday)
        return "{} {}, {} {}, {} {}{}".format(
            diff.years,
            "year" + self.format_plural(diff.years),
            diff.months,
            "month" + self.format_plural(diff.months),
            diff.days,
            "day" + self.format_plural(diff.days),
            " 🎂" if (diff.months == 0 and diff.days == 0) else "",
        )

    def fetch_all_pages(
        self, query: str, variables: dict = {}, page_size: int = 100
    ) -> list:
        variables = {**variables, "first": page_size, "cursor": None}
        items = []

        while True:
            print("run")
            response = requests.post(
                "https://api.github.com/graphql",
                json={"query": query, "variables": variables},
                headers=self.headers,
            )
            data = response.json()["data"]

            # Walk the response to find nodes/edges and pageInfo
            def find(obj, key):
                if isinstance(obj, dict):
                    if key in obj:
                        return obj[key]
                    for v in obj.values():
                        r = find(v, key)
                        if r is not None:
                            return r

            nodes = find(data, "nodes") or [
                e["node"] for e in (find(data, "edges") or [])
            ]
            page_info = find(data, "pageInfo")

            items.extend(nodes)

            if not page_info or not page_info["hasNextPage"]:
                break
            variables["cursor"] = page_info["endCursor"]

        return items

    def format_plural(self, unit):
        """
        Returns a properly formatted number e.g.
        >>> '5 days'
        'day' + format_plural(diff.days) == 5
        >>> '1 day'
        'day' + format_plural(diff.days) == 1
        """
        return "s" if unit != 1 else ""

    def update_all_repositories(self):
        query = """
        query ($first: Int, $cursor: String, $owner_affiliation: [RepositoryAffiliation]!) {
            viewer {
                repositories(first: $first, after: $cursor, ownerAffiliations: $owner_affiliation) {
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                    nodes {
                        id
                        name
                        stargazerCount
                    }
                }
            }
        }
        """
        variables = {"owner_affiliation": self.scope}
        result = self.fetch_all_pages(query=query, variables=variables, page_size=100)

        self.update_cache_with_stats(result)

    def get_commit_stats(self, repo_id):
        query = """
        query($repo_id: ID!, $author_id: ID!, $cursor: String) {
            node(id: $repo_id) {
                ... on Repository {
                    object(expression: "HEAD") {
                        ... on Commit {
                            history(author: {id: $author_id}, first: 100, after: $cursor) {
                                totalCount
                                pageInfo { hasNextPage endCursor }
                                nodes { additions deletions }
                            }
                        }
                    }
                }
            }
        }
        """
        all_history = self.fetch_all_pages(
            query, {"repo_id": repo_id, "author_id": self.user_id}
        )

        # Summing stats across all paginated commit nodes
        total_additions = sum(node["additions"] for node in all_history if node)
        total_deletions = sum(node["deletions"] for node in all_history if node)

        return {
            "total_commits": len(all_history),
            "additions": total_additions,
            "deletions": total_deletions,
        }

    def update_cache_with_stats(self, repo_results):
        cache = {}

        a, b, c, d = [0, 0, 0, 0]
        for node in repo_results:
            repo_id = node["id"]
            stats = self.get_commit_stats(repo_id)

            hashed_name = hashlib.sha256(repo_id.encode()).hexdigest()[:12]
            cache[hashed_name] = {
                "commits": stats["total_commits"],
                "stars": node["stargazerCount"],
                "additions": stats["additions"],
                "deletions": stats["deletions"],
            }
            a += stats["total_commits"]
            b += node["stargazerCount"]
            c += stats["additions"]
            d += stats["deletions"]

        print(a, b, c, d)

        with open(self.cache_filename, "w") as f:
            json.dump(cache, f, indent=4)

    def svg_overwrite(
        self,
        filename,
        uptime,
        stars,
        repos,
        commits,
        followers,
        loc_data,
    ):
        """
        Parse SVG files and update elements with my age, commits, stars, repositories, and lines written
        """
        tree = etree.parse(filename)  # type: ignore
        root = tree.getroot()
        self.justify_format(root, "uptime", uptime, 0)
        self.justify_format(root, "stars", stars, 0)
        self.justify_format(root, "repos", repos, 0)
        self.justify_format(root, "commits", commits, 0)
        self.justify_format(root, "followers", followers, 0)
        self.justify_format(root, "lines", loc_data[2], 0)
        self.justify_format(root, "added", loc_data[0], 0)
        self.justify_format(root, "deleted", loc_data[1], 0)
        tree.write(filename, encoding="utf-8", xml_declaration=True)

    def justify_format(self, root, element_id, new_text, length=0):
        """
        Updates and formats the text of the element, and modifes the amount of dots in the previous element to justify the new text on the svg
        """
        if isinstance(new_text, int):
            new_text = f"{'{:,}'.format(new_text)}"
        new_text = str(new_text)
        self.find_and_replace(root, element_id, new_text)
        just_len = max(0, length - len(new_text))
        if just_len <= 2:
            dot_map = {0: "", 1: " ", 2: ". "}
            dot_string = dot_map[just_len]
        else:
            dot_string = " " + ("." * just_len) + " "
        self.find_and_replace(root, f"{element_id}_dots", dot_string)

    def find_and_replace(self, root, element_id, new_text):
        """
        Finds the element in the SVG file and replaces its text with a new value
        """
        element = root.find(f".//*[@id='{element_id}']")
        if element is not None:
            element.text = new_text

    def follower_getter(self) -> int:
        """
        Returns the number of followers of the user
        """
        query = """
        query($login: String!){
            user(login: $login) {
                followers {
                    totalCount
                }
            }
        }"""

        request = requests.post(
            "https://api.github.com/graphql",
            json={"query": query, "variables": {"login": self.username}},
            headers=self.headers,
        )
        return int(request.json()["data"]["user"]["followers"]["totalCount"])

    def get_cached_data(self):
        self.update_all_repositories()

        cache = (
            json.load(open(self.cache_filename))
            if os.path.exists(self.cache_filename)
            else {}
        )
        return cache


def main():
    stats_obj = Stats()
    uptime = stats_obj.get_age()
    cache_data = stats_obj.get_cached_data()

    commits = 0
    added = 0
    deleted = 0

    for name, info in cache_data.items():
        print(
            f"{name}: +{info['additions']}, -{info['deletions']}, commits: {info['commits']}"
        )
        commits += info["commits"]
        added += info["additions"]
        deleted += info["deletions"]

    stars = "7"
    repos = len(cache_data)
    followers = stats_obj.follower_getter()

    total_loc = [added, deleted, added - deleted]

    for index in range(len(total_loc) - 1):
        total_loc[index] = "{:,}".format(total_loc[index])

    stats_obj.svg_overwrite(
        filename="dark_mode.svg",
        uptime=uptime,
        stars=stars,
        repos=repos,
        commits=commits,
        followers=followers,
        loc_data=total_loc,
    )


main()
