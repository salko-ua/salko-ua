import os
import hashlib
import requests
from lxml import etree
from datetime import datetime as dt
from dateutil import relativedelta

class Stats:
    def __init__(self) -> None:
        self.headers = {'authorization': 'token ' + os.environ['ACCESS_TOKEN']}
        self.username = "salko-ua"
        self.query_count = {
            'user_getter': 0,
            'follower_getter': 0,
            'graph_repos_stars': 0,
            'recursive_loc': 0,
            'graph_commits': 0,
            'loc_query': 0
        }

        # MAIN
        self.os = "Linux (NixOS 25.05)"
        self.birthday = dt(2006, 3, 28)
        self.host = "Ukraine"
        self.kernel = "Volyn, Lutsk"
        self.ide = "Lazy Nvim v0.11.2"

        # STACK
        self.programming = "Python, JavaScript, VBA, SQL"
        self.frontend = "Svelte, Tailwind CSS"
        self.backend = "FastAPI, SQLAlchemy, Docker"
        self.database = "PostgreSQL, MONGODB, SQLite, Redis"
        self.other = "HTML, CSS, JSON, MARKDOWN"

    def add_query_count(self, funct_id):
        """
        Counts how many times the GitHub GraphQL API is called
        """
        self.query_count[funct_id] += 1

    def get_age(self) -> str:
        """
        Returns the length of time since I was born e.g.
        >>> 'XX years, XX months, XX days'
        """
        diff = relativedelta.relativedelta(dt.today(), self.birthday)
        return '{} {}, {} {}, {} {}{}'.format(
            diff.years, 'year' + self.format_plural(diff.years),
            diff.months, 'month' + self.format_plural(diff.months),
            diff.days, 'day' + self.format_plural(diff.days),
            ' 🎂' if (diff.months == 0 and diff.days == 0) else '')

    def format_plural(self, unit):
        """
        Returns a properly formatted number e.g.
        >>> '5 days'
        'day' + format_plural(diff.days) == 5
        >>> '1 day'
        'day' + format_plural(diff.days) == 1
        """
        return 's' if unit != 1 else ''

    def request_wrapper(self, func_name, query, variables):
        """
        Returns a request, or raises an Exception if the response does not succeed.
        """
        request = requests.post('https://api.github.com/graphql', json={'query': query, 'variables':variables}, headers=self.headers)
        if request.status_code == 200:
            return request
        raise Exception(func_name, ' has failed with a', request.status_code, request.text, self.query_count)

    def graph_repos_stars(self, count_type, owner_affiliation, cursor=None, add_loc=0, del_loc=0):
        """
        Uses GitHub's GraphQL v4 API to return my total repository, star, or lines of code count.
        """
        self.add_query_count('graph_repos_stars')
        query = '''
        query ($owner_affiliation: [RepositoryAffiliation], $login: String!, $cursor: String) {
            user(login: $login) {
                repositories(first: 100, after: $cursor, ownerAffiliations: $owner_affiliation) {
                    totalCount
                    edges {
                        node {
                            ... on Repository {
                                nameWithOwner
                                stargazers {
                                    totalCount
                                }
                            }
                        }
                    }
                    pageInfo {
                        endCursor
                        hasNextPage
                    }
                }
            }
        }'''
        variables = {'owner_affiliation': owner_affiliation, 'login': self.username, 'cursor': cursor}
        request = self.request_wrapper(self.graph_repos_stars.__name__, query, variables)
        if request.status_code == 200:
            if count_type == 'repos':
                return request.json()['data']['user']['repositories']['totalCount']
            elif count_type == 'stars':
                return self.stars_counter(request.json()['data']['user']['repositories']['edges'])

    def stars_counter(self, data):
        """
        Count total stars in repositories owned by me
        """
        total_stars = 0
        for node in data: total_stars += node['node']['stargazers']['totalCount']
        return total_stars


    def recursive_loc(
        self,
        owner,
        repo_name,
        data,
        cache_comment,
        addition_total=0,
        deletion_total=0,
        my_commits=0,
        cursor=None
    ):
        """
        Uses GitHub's GraphQL v4 API and cursor pagination to fetch 100 commits from a repository at a time
        """
        self.add_query_count('recursive_loc')
        query = '''
        query ($repo_name: String!, $owner: String!, $cursor: String) {
            repository(name: $repo_name, owner: $owner) {
                defaultBranchRef {
                    target {
                        ... on Commit {
                            history(first: 100, after: $cursor) {
                                totalCount
                                edges {
                                    node {
                                        ... on Commit {
                                            committedDate
                                        }
                                        author {
                                            user {
                                                id
                                            }
                                        }
                                        deletions
                                        additions
                                    }
                                }
                                pageInfo {
                                    endCursor
                                    hasNextPage
                                }
                            }
                        }
                    }
                }
            }
        }'''
        variables = {'repo_name': repo_name, 'owner': owner, 'cursor': cursor}
        request = requests.post('https://api.github.com/graphql', json={'query': query, 'variables':variables}, headers=self.headers) # I cannot use request_wrapper(), because I want to save the file before raising Exception
        if request.status_code == 200:
            if request.json()['data']['repository']['defaultBranchRef'] != None: # Only count commits if repo isn't empty
                return self.loc_counter_one_repo(owner, repo_name, data, cache_comment, request.json()['data']['repository']['defaultBranchRef']['target']['history'], addition_total, deletion_total, my_commits)
            else: return 0
        self.force_close_file(data, cache_comment) # saves what is currently in the file before this program crashes
        if request.status_code == 403:
            raise Exception('Too many requests in a short amount of time!\nYou\'ve hit the non-documented anti-abuse limit!')
        raise Exception('recursive_loc() has failed with a', request.status_code, request.text, self.query_count)


    def loc_counter_one_repo(self, owner, repo_name, data, cache_comment, history, addition_total, deletion_total, my_commits):
        """
        Recursively call recursive_loc (since GraphQL can only search 100 commits at a time)
        only adds the LOC value of commits authored by me
        """
        for node in history['edges']:
            if node['node']['author']['user'] == self.owner_id:
                my_commits += 1
                addition_total += node['node']['additions']
                deletion_total += node['node']['deletions']

        if history['edges'] == [] or not history['pageInfo']['hasNextPage']:
            return addition_total, deletion_total, my_commits
        else: return self.recursive_loc(owner, repo_name, data, cache_comment, addition_total, deletion_total, my_commits, history['pageInfo']['endCursor'])


    def loc_query(self, owner_affiliation, comment_size=0, force_cache=False, cursor=None, edges=[]):
        """
        Uses GitHub's GraphQL v4 API to query all the repositories I have access to (with respect to owner_affiliation)
        Queries 60 repos at a time, because larger queries give a 502 timeout error and smaller queries send too many
        requests and also give a 502 error.
        Returns the total number of lines of code in all repositories
        """
        self.add_query_count('loc_query')
        query = '''
        query ($owner_affiliation: [RepositoryAffiliation], $login: String!, $cursor: String) {
            user(login: $login) {
                repositories(first: 60, after: $cursor, ownerAffiliations: $owner_affiliation) {
                edges {
                    node {
                        ... on Repository {
                            nameWithOwner
                            defaultBranchRef {
                                target {
                                    ... on Commit {
                                        history {
                                            totalCount
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                    pageInfo {
                        endCursor
                        hasNextPage
                    }
                }
            }
        }'''
        variables = {'owner_affiliation': owner_affiliation, 'login': self.username, 'cursor': cursor}
        request = self.request_wrapper(self.loc_query.__name__, query, variables)
        if request.json()['data']['user']['repositories']['pageInfo']['hasNextPage']:   # If repository data has another page
            edges += request.json()['data']['user']['repositories']['edges']            # Add on to the LoC count
            return self.loc_query(owner_affiliation, comment_size, force_cache, request.json()['data']['user']['repositories']['pageInfo']['endCursor'], edges)
        else:
            return self.cache_builder(edges + request.json()['data']['user']['repositories']['edges'], comment_size, force_cache)


    def cache_builder(self, edges, comment_size, force_cache, loc_add=0, loc_del=0):
        """
        Checks each repository in edges to see if it has been updated since the last time it was cached
        If it has, run recursive_loc on that repository to update the LOC count
        """
        cached = True # Assume all repositories are cached
        filename = 'cache/'+hashlib.sha256(self.username.encode('utf-8')).hexdigest()+'.txt' # Create a unique filename for each user
        try:
            with open(filename, 'r') as f:
                data = f.readlines()
        except FileNotFoundError: # If the cache file doesn't exist, create it
            data = []
            if comment_size > 0:
                for _ in range(comment_size): data.append('This line is a comment block. Write whatever you want here.\n')
            with open(filename, 'w') as f:
                f.writelines(data)

        if len(data)-comment_size != len(edges) or force_cache: # If the number of repos has changed, or force_cache is True
            cached = False
            self.flush_cache(edges, filename, comment_size)
            with open(filename, 'r') as f:
                data = f.readlines()

        cache_comment = data[:comment_size] # save the comment block
        data = data[comment_size:] # remove those lines
        for index in range(len(edges)):
            repo_hash, commit_count, *__ = data[index].split()
            if repo_hash == hashlib.sha256(edges[index]['node']['nameWithOwner'].encode('utf-8')).hexdigest():
                try:
                    if int(commit_count) != edges[index]['node']['defaultBranchRef']['target']['history']['totalCount']:
                        # if commit count has changed, update loc for that repo
                        owner, repo_name = edges[index]['node']['nameWithOwner'].split('/')
                        loc = self.recursive_loc(owner, repo_name, data, cache_comment)
                        data[index] = repo_hash + ' ' + str(edges[index]['node']['defaultBranchRef']['target']['history']['totalCount']) + ' ' + str(loc[2]) + ' ' + str(loc[0]) + ' ' + str(loc[1]) + '\n'
                except TypeError: # If the repo is empty
                    data[index] = repo_hash + ' 0 0 0 0\n'
        with open(filename, 'w') as f:
            f.writelines(cache_comment)
            f.writelines(data)
        for line in data:
            loc = line.split()
            loc_add += int(loc[3])
            loc_del += int(loc[4])
        return [loc_add, loc_del, loc_add - loc_del, cached]


    def flush_cache(self, edges, filename, comment_size):
        """
        Wipes the cache file
        This is called when the number of repositories changes or when the file is first created
        """
        with open(filename, 'r') as f:
            data = []
            if comment_size > 0:
                data = f.readlines()[:comment_size] # only save the comment
        with open(filename, 'w') as f:
            f.writelines(data)
            for node in edges:
                f.write(hashlib.sha256(node['node']['nameWithOwner'].encode('utf-8')).hexdigest() + ' 0 0 0 0\n')


    def add_archive(self):
        """
        Several repositories I have contributed to have since been deleted.
        This function adds them using their last known data
        """
        with open('cache/repository_archive.txt', 'r') as f:
            data = f.readlines()
        old_data = data
        data = data[7:len(data)-3] # remove the comment block
        added_loc, deleted_loc, added_commits = 0, 0, 0
        contributed_repos = len(data)
        for line in data:
            repo_hash, total_commits, my_commits, *loc = line.split()
            added_loc += int(loc[0])
            deleted_loc += int(loc[1])
            if (my_commits.isdigit()): added_commits += int(my_commits)
        added_commits += int(old_data[-1].split()[4][:-1])
        return [added_loc, deleted_loc, added_loc - deleted_loc, added_commits, contributed_repos]

    def force_close_file(self, data, cache_comment):
        """
        Forces the file to close, preserving whatever data was written to it
        This is needed because if this function is called, the program would've crashed before the file is properly saved and closed
        """
        filename = 'cache/'+hashlib.sha256(self.username.encode('utf-8')).hexdigest()+'.txt'
        with open(filename, 'w') as f:
            f.writelines(cache_comment)
            f.writelines(data)
        print('There was an error while writing to the cache file. The file,', filename, 'has had the partial data saved and closed.')


    def stars_counter(self, data):
        """
        Count total stars in repositories owned by me
        """
        total_stars = 0
        for node in data: total_stars += node['node']['stargazers']['totalCount']
        return total_stars


    def svg_overwrite(self, filename, age_data, commit_data, star_data, repo_data, contrib_data, follower_data, loc_data):
        """
        Parse SVG files and update elements with my age, commits, stars, repositories, and lines written
        """
        tree = etree.parse(filename)
        root = tree.getroot()
        self.justify_format(root, "age_data", age_data, 50)
        self.justify_format(root, 'commit_data', commit_data, 50)
        self.justify_format(root, 'star_data', star_data, 10)
        self.justify_format(root, 'repo_data', repo_data, 10)
        self.justify_format(root, 'contrib_data', contrib_data, 10)
        self.justify_format(root, 'follower_data', follower_data, 10)
        self.justify_format(root, 'loc_data', loc_data[2], 10)
        self.justify_format(root, 'loc_add', loc_data[0], 10)
        self.justify_format(root, 'loc_del', loc_data[1], 10)
        tree.write(filename, encoding='utf-8', xml_declaration=True)


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
            dot_map = {0: '', 1: ' ', 2: '. '}
            dot_string = dot_map[just_len]
        else:
            dot_string = ' ' + ('.' * just_len) + ' '
        self.find_and_replace(root, f"{element_id}_dots", dot_string)


    def find_and_replace(self, root, element_id, new_text):
        """
        Finds the element in the SVG file and replaces its text with a new value
        """
        element = root.find(f".//*[@id='{element_id}']")
        if element is not None:
            element.text = new_text


    def commit_counter(self, comment_size):
        """
        Counts up my total commits, using the cache file created by cache_builder.
        """
        total_commits = 0
        filename = 'cache/'+hashlib.sha256(self.username.encode('utf-8')).hexdigest()+'.txt' # Use the same filename as cache_builder
        with open(filename, 'r') as f:
            data = f.readlines()
        cache_comment = data[:comment_size] # save the comment block
        data = data[comment_size:] # remove those lines
        for line in data:
            total_commits += int(line.split()[2])
        return total_commits


    def user_getter(self) -> dict:
        """
        Returns the account ID and creation time of the user
        """
        self.add_query_count('user_getter')
        query = '''
        query($login: String!){
            user(login: $login) {
                id
                createdAt
            }
        }'''
        variables = {'login': self.username}
        request = self.request_wrapper(self.user_getter.__name__, query, variables)
        return {'id': request.json()['data']['user']['id']}, request.json()['data']['user']['createdAt']

    def follower_getter(self) -> int:
        """
        Returns the number of followers of the user
        """
        self.add_query_count('follower_getter')
        query = '''
        query($login: String!){
            user(login: $login) {
                followers {
                    totalCount
                }
            }
        }'''
        request = self.request_wrapper(self.follower_getter.__name__, query, {'login': self.username})
        return int(request.json()['data']['user']['followers']['totalCount'])


def main():
    stats = Stats()
    """Main function to run the script and print the results"""
    print('Calculation times:')
    user_data = stats.user_getter()
    owner_id, acc_date = user_data
    stats.owner_id = owner_id
    print(user_data)

    age_data = stats.get_age()
    print(age_data)

    total_loc = stats.loc_query(['OWNER'], 7)
    print(total_loc)

    commit_data = stats.commit_counter(7)
    star_data = stats.graph_repos_stars('stars', ['OWNER'])
    repo_data =  stats.graph_repos_stars('repos', ['OWNER'])
    contrib_data =  stats.graph_repos_stars('repos', ['OWNER', 'COLLABORATOR', 'ORGANIZATION_MEMBER'])
    follower_data =  stats.follower_getter()

    if owner_id == "U_kgDOB3WZHg":
        archived_data = stats.add_archive()
        for index in range(len(total_loc)-1):
            total_loc[index] += archived_data[index]
        contrib_data += archived_data[-1]
        commit_data += int(archived_data[-2])

    for index in range(len(total_loc)-1): total_loc[index] = '{:,}'.format(total_loc[index]) # format added, deleted, and total LOC

    stats.svg_overwrite('dark_mode.svg', age_data, commit_data, star_data, repo_data, contrib_data, follower_data, total_loc[:-1])

    print('Total GitHub GraphQL API calls:', '{:>3}'.format(sum(stats.query_count.values())))
    for funct_name, count in stats.query_count.items(): print('{:<28}'.format('   ' + funct_name + ':'), '{:>6}'.format(count))

main()
