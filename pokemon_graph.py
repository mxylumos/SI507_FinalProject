import requests
import json
import os
import time
from typing import Dict, List, Optional, Any, Tuple
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import networkx as nx
from functools import lru_cache


# ==================== Abstract Base Class Definitions ====================

class DataSource(ABC):
    """Data source abstract base class - defines a unified interface for all data sources"""

    @abstractmethod
    def load(self, **kwargs) -> Any:
        """Abstract method for loading data"""
        pass

    @abstractmethod
    def get_cache_key(self) -> str:
        """Return the cache key name"""
        pass


class CacheManager:
    """Cache manager - responsible for all data source caching operations"""

    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def get_cache_path(self, key: str) -> str:
        return os.path.join(self.cache_dir, f"{key}.json")

    def has_cache(self, key: str) -> bool:
        return os.path.exists(self.get_cache_path(key))

    def save(self, key: str, data: Any):
        with open(self.get_cache_path(key), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self, key: str) -> Any:
        with open(self.get_cache_path(key), "r", encoding="utf-8") as f:
            return json.load(f)


class CentralityStrategy(ABC):
    """Abstract base class for centrality calculation strategies"""

    @abstractmethod
    def calculate(self, graph: nx.Graph) -> Dict[str, float]:
        """Calculate centrality"""
        pass


class DegreeCentrality(CentralityStrategy):
    """Degree centrality strategy"""

    def calculate(self, graph: nx.Graph) -> Dict[str, float]:
        return nx.degree_centrality(graph)


class BetweennessCentrality(CentralityStrategy):
    """Betweenness centrality strategy"""

    def calculate(self, graph: nx.Graph) -> Dict[str, float]:
        return nx.betweenness_centrality(graph)


class ClosenessCentrality(CentralityStrategy):
    """Closeness centrality strategy"""

    def calculate(self, graph: nx.Graph) -> Dict[str, float]:
        return nx.closeness_centrality(graph)


# ==================== Data Class Definitions ====================

@dataclass
class Pokemon:
    """Pokémon data class - simplified using dataclass"""
    id: int
    name: str
    types: List[str]
    sprite: str
    stats: Dict[str, int]
    habitat: Optional[str] = None
    color: Optional[str] = None
    shape: Optional[str] = None
    generation: Optional[int] = None
    is_legendary: bool = False
    height: Optional[float] = None
    weight: Optional[float] = None

    def __post_init__(self):
        self.name = self.name.lower()

    @property
    def primary_type(self) -> Optional[str]:
        """Get primary type"""
        return self.types[0] if self.types else None

    @property
    def total_stats(self) -> int:
        """Total base stats"""
        return sum(self.stats.values())

    def __repr__(self) -> str:
        types_str = "/".join(self.types)
        habitat_str = f" [{self.habitat}]" if self.habitat else ""
        return f"{self.name.capitalize()}({types_str}){habitat_str}"


# ==================== Concrete Data Source Implementations ====================

class PokeAPISource(DataSource):
    """PokéAPI data source - basic Pokémon data"""

    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
        self.base_url = "https://pokeapi.co/api/v2"

    def get_cache_key(self) -> str:
        return "pokemon_basic"

    def load(self, limit: int = 151, force_refresh: bool = False) -> Dict:
        """Load basic Pokémon data"""
        cache_key = self.get_cache_key()

        if not force_refresh and self.cache_manager.has_cache(cache_key):
            print("Loading basic Pokémon data from cache...")
            return self.cache_manager.load(cache_key)

        print("Downloading basic Pokémon data from PokéAPI...")
        data = {}

        # Get Pokémon list
        resp = requests.get(f"{self.base_url}/pokemon?limit={limit}")
        pokemon_list = resp.json()["results"]

        # Add progress display
        for i, p in enumerate(pokemon_list, 1):
            print(f"Download progress: {i}/{limit}", end="\r")

            try:
                detail = requests.get(p["url"]).json()

                types = [t["type"]["name"] for t in detail["types"]]
                sprite = detail["sprites"]["front_default"] or ""
                stats = {s["stat"]["name"]: s["base_stat"] for s in detail["stats"]}

                data[detail["name"]] = {
                    "id": detail["id"],
                    "types": types,
                    "sprite": sprite,
                    "stats": stats,
                    "height": detail["height"],
                    "weight": detail["weight"]
                }

                time.sleep(0.1)  # Avoid too many requests

            except Exception as e:
                print(f"Error downloading {p['name']}: {e}")
                continue

        print("\nDownload completed, saving to cache...")
        self.cache_manager.save(cache_key, data)
        return data


class EvolutionSource(DataSource):
    """Evolution chain data source"""

    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
        self.base_url = "https://pokeapi.co/api/v2"

    def get_cache_key(self) -> str:
        return "evolution_chains"

    def load(self, limit: int = 151, force_refresh: bool = False) -> List:
        """Load evolution chain data"""
        cache_key = self.get_cache_key()

        if not force_refresh and self.cache_manager.has_cache(cache_key):
            print("Loading evolution chain data from cache...")
            return self.cache_manager.load(cache_key)

        print("Downloading evolution chain data from PokéAPI...")
        chains = []

        for i in range(1, limit + 1):
            try:
                r = requests.get(f"{self.base_url}/evolution-chain/{i}")
                if r.status_code == 200:
                    chain = r.json()["chain"]
                    pairs = self._parse_evolution_chain(chain)
                    chains.extend(pairs)
                time.sleep(0.1)
            except Exception as e:
                print(f"Error downloading evolution chain {i}: {e}")
                continue

        print("Evolution chain download completed, saving to cache...")
        self.cache_manager.save(cache_key, chains)
        return chains

    def _parse_evolution_chain(self, chain) -> List:
        """Recursively parse evolution chain"""
        pairs = []
        species = chain["species"]["name"]

        for evo in chain.get("evolves_to", []):
            next_name = evo["species"]["name"]
            level = None

            if evo.get("evolution_details"):
                level = evo["evolution_details"][0].get("min_level")

            pairs.append((species, next_name, level))
            pairs.extend(self._parse_evolution_chain(evo))

        return pairs


class HabitatSource(DataSource):
    """Habitat data source - the second data source"""

    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
        self.base_url = "https://pokeapi.co/api/v2"

    def get_cache_key(self) -> str:
        return "habitat_data"

    def load(self, force_refresh: bool = False) -> Dict[str, Dict]:
        """Load Pokémon habitat data"""
        cache_key = self.get_cache_key()

        if not force_refresh and self.cache_manager.has_cache(cache_key):
            print("Loading habitat data from cache...")
            return self.cache_manager.load(cache_key)

        print("Downloading habitat data from PokéAPI...")
        habitat_data = {}

        # Get all habitats
        resp = requests.get(f"{self.base_url}/pokemon-habitat/")
        habitats = resp.json()["results"]

        for habitat in habitats:
            habitat_name = habitat["name"]
            print(f"Processing habitat: {habitat_name}")

            detail = requests.get(habitat["url"]).json()

            # Get all Pokémon in this habitat
            for pokemon in detail["pokemon_species"]:
                pokemon_name = pokemon["name"]

                if pokemon_name not in habitat_data:
                    habitat_data[pokemon_name] = {
                        "primary_habitat": habitat_name,
                        "all_habitats": [habitat_name]
                    }
                else:
                    if habitat_name not in habitat_data[pokemon_name]["all_habitats"]:
                        habitat_data[pokemon_name]["all_habitats"].append(habitat_name)

            time.sleep(0.2)

        # Add Pokémon color data as supplement
        self._add_color_data(habitat_data)

        print("Habitat data download completed, saving to cache...")
        self.cache_manager.save(cache_key, habitat_data)
        return habitat_data

    def _add_color_data(self, habitat_data: Dict):
        """Add Pokémon color data"""
        resp = requests.get(f"{self.base_url}/pokemon-color/")
        colors = resp.json()["results"]

        for color in colors:
            color_name = color["name"]
            detail = requests.get(color["url"]).json()

            for pokemon in detail["pokemon_species"]:
                pokemon_name = pokemon["name"]
                if pokemon_name in habitat_data:
                    habitat_data[pokemon_name]["color"] = color_name


# ==================== Graph Core Class ====================

class PokemonGraph:
    """Pokémon graph core class - supports multiple relationship types"""

    def __init__(self):
        self.graph = nx.MultiDiGraph()  # Use MultiDiGraph to support multiple edges
        self.pokemon_dict: Dict[str, Pokemon] = {}
        self.cache_manager = CacheManager()

        # Centrality calculation strategy
        self.centrality_strategy: CentralityStrategy = DegreeCentrality()

    def set_centrality_strategy(self, strategy: CentralityStrategy):
        """Set centrality calculation strategy"""
        self.centrality_strategy = strategy

    def add_pokemon(self, pokemon: Pokemon):
        """Add Pokémon node"""
        self.pokemon_dict[pokemon.name] = pokemon
        self.graph.add_node(pokemon.name,
                            data=pokemon,
                            types=pokemon.types,
                            habitat=pokemon.habitat)

    def add_evolution_edge(self, from_name: str, to_name: str,
                           level: Optional[int] = None):
        """Add evolution edge"""
        if from_name in self.graph and to_name in self.graph:
            self.graph.add_edge(from_name, to_name,
                                weight=level or 1,
                                relation='evolution',
                                level=level)

    def add_type_similarity_edge(self, p1: str, p2: str, shared_count: int):
        """Add type similarity edge"""
        if p1 != p2 and shared_count > 0:
            self.graph.add_edge(p1, p2,
                                weight=shared_count,
                                relation='type_similarity',
                                shared_types=shared_count)

    def add_habitat_edge(self, p1: str, p2: str):
        """Add habitat similarity edge (insight from the second data source)"""
        if p1 != p2:
            pokemon1 = self.pokemon_dict.get(p1)
            pokemon2 = self.pokemon_dict.get(p2)

            if pokemon1 and pokemon2 and pokemon1.habitat and pokemon2.habitat:
                if pokemon1.habitat == pokemon2.habitat:
                    self.graph.add_edge(p1, p2,
                                        weight=2,
                                        relation='same_habitat',
                                        habitat=pokemon1.habitat)

    def find_shortest_path(self, start: str, end: str,
                           relation_filter: Optional[str] = None) -> List[str]:
        """Find shortest path, can filter by relationship type"""
        try:
            if relation_filter:
                # For MultiDiGraph, edge keys must be included
                edges_to_keep = [(u, v, k) for u, v, k, d in self.graph.edges(keys=True, data=True)
                                 if d.get('relation') == relation_filter]

                if not edges_to_keep:
                    return []

                # Create filtered subgraph
                subgraph = self.graph.edge_subgraph(edges_to_keep)
                # Convert to undirected graph for path finding
                undirected = nx.Graph(subgraph.to_undirected())
                return nx.shortest_path(undirected, start.lower(), end.lower())
            else:
                return nx.shortest_path(self.graph.to_undirected(),
                                        start.lower(), end.lower())
        except (nx.NetworkXNoPath, nx.NodeNotFound, nx.NetworkXError):
            return []

    def get_centrality_ranking(self, top_n: int = 10) -> List[Tuple[str, float]]:
        """Get centrality ranking"""
        # Use current strategy to calculate centrality
        centrality = self.centrality_strategy.calculate(self.graph.to_undirected())
        return sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:top_n]

    def get_pokemon_by_habitat(self, habitat: str) -> List[Pokemon]:
        """Get Pokémon by habitat (insight from the second data source)"""
        return [p for p in self.pokemon_dict.values()
                if p.habitat == habitat]

    def get_habitat_clusters(self) -> Dict[str, List[str]]:
        """Get habitat clusters (graph structure insight)"""
        clusters = {}
        for name, pokemon in self.pokemon_dict.items():
            if pokemon.habitat:
                if pokemon.habitat not in clusters:
                    clusters[pokemon.habitat] = []
                clusters[pokemon.habitat].append(name)
        return clusters

    def find_type_habitat_correlation(self) -> List[str]:
        """Discover type-habitat correlation (graph structure insight)"""
        insights = []
        type_habitat_map = {}

        for pokemon in self.pokemon_dict.values():
            if pokemon.types and pokemon.habitat:
                for t in pokemon.types:
                    if t not in type_habitat_map:
                        type_habitat_map[t] = {}
                    type_habitat_map[t][pokemon.habitat] = type_habitat_map[t].get(pokemon.habitat, 0) + 1

        # Find the most common habitat for each type
        for ptype, habitats in type_habitat_map.items():
            if habitats:
                most_common = max(habitats.items(), key=lambda x: x[1])
                insights.append(f"🔍 {ptype} type Pokémon are most commonly found in the {most_common[0]} habitat")

        return insights

    def generate_path_narrative(self, path: List[str]) -> str:
        """Generate path story"""
        if not path:
            return "No path found!"

        story_parts = []
        for i in range(len(path) - 1):
            current = path[i]
            next_poke = path[i + 1]

            # Check edge relationship type
            if self.graph.has_edge(current, next_poke):
                edge_data = self.graph.get_edge_data(current, next_poke)
                if edge_data:
                    # Take data from the first edge
                    first_edge = next(iter(edge_data.values()))
                    relation = first_edge.get('relation', 'unknown')

                    if relation == 'evolution':
                        level = first_edge.get('level')
                        level_text = f"at level {level}" if level else "in some way"
                        story_parts.append(f"{current.capitalize()} {level_text} evolved into {next_poke.capitalize()}")
                    elif relation == 'same_habitat':
                        habitat = first_edge.get('habitat', 'the same')
                        story_parts.append(
                            f"{current.capitalize()} and {next_poke.capitalize()} both live in the {habitat} habitat")
                    elif relation == 'type_similarity':
                        story_parts.append(f"{current.capitalize()} and {next_poke.capitalize()} share the same type")

        if story_parts:
            return "🌟 Adventure Story:\n" + "\n".join(story_parts)
        else:
            return " → ".join(p.capitalize() for p in path)


class DataLoader:
    """Data loader - integrates all data sources"""

    def __init__(self):
        self.cache_manager = CacheManager()

        # Initialize each data source
        self.pokeapi_source = PokeAPISource(self.cache_manager)
        self.evolution_source = EvolutionSource(self.cache_manager)
        self.habitat_source = HabitatSource(self.cache_manager)

    def load_all_data(self, limit: int = 151) -> Tuple[Dict, List, Dict]:
        """Load all data"""
        # 1. Load basic data
        pokemon_data = self.pokeapi_source.load(limit=limit)
        # 2. Load evolution chains
        evo_chains = self.evolution_source.load(limit=limit)
        # 3. Load habitat data (second data source)
        habitat_data = self.habitat_source.load()
        # 4. Merge habitat data into Pokémon data
        for pokemon_name, data in pokemon_data.items():
            if pokemon_name in habitat_data:
                habitat_info = habitat_data[pokemon_name]
                data['habitat'] = habitat_info.get('primary_habitat')
                data['color'] = habitat_info.get('color')

        return pokemon_data, evo_chains, habitat_data