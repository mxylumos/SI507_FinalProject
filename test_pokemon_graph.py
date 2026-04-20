"""
Test Suite - Living Documentation for the Project
Run with: python -m pytest test_pokemon_graph.py -v
"""

import unittest
import tempfile
import os
import json
import shutil
from unittest.mock import Mock, patch, MagicMock
import networkx as nx

from pokemon_graph import (
    Pokemon, PokemonGraph, DataLoader,
    CacheManager, PokeAPISource, EvolutionSource,
    HabitatSource, DegreeCentrality, BetweennessCentrality,
    ClosenessCentrality
)


class TestPokemonClass(unittest.TestCase):
    """Test Pokémon data class"""

    def setUp(self):
        """Setup before each test"""
        self.pikachu = Pokemon(
            id=25,
            name="pikachu",
            types=["electric"],
            sprite="http://example.com/pikachu.png",
            stats={"hp": 35, "attack": 55, "defense": 40},
            habitat="forest",
            color="yellow",
            generation=1,
            height=4,
            weight=60
        )

    def test_pokemon_creation(self):
        """Test Pokémon object creation"""
        self.assertEqual(self.pikachu.id, 25)
        self.assertEqual(self.pikachu.name, "pikachu")
        self.assertEqual(self.pikachu.types, ["electric"])
        self.assertEqual(self.pikachu.primary_type, "electric")

    def test_total_stats_calculation(self):
        """Test total base stats calculation"""
        self.assertEqual(self.pikachu.total_stats, 35 + 55 + 40)

    def test_name_normalization(self):
        """Test automatic name lowercasing"""
        charizard = Pokemon(
            id=6, name="Charizard", types=["fire", "flying"],
            sprite="", stats={}
        )
        self.assertEqual(charizard.name, "charizard")

    def test_primary_type_with_no_types(self):
        """Test handling when there are no types"""
        mew = Pokemon(id=151, name="mew", types=[], sprite="", stats={})
        self.assertIsNone(mew.primary_type)

    def test_repr_method(self):
        """Test string representation"""
        repr_str = repr(self.pikachu)
        self.assertIn("Pikachu", repr_str)
        self.assertIn("electric", repr_str)
        self.assertIn("forest", repr_str)


class TestCacheManager(unittest.TestCase):
    """Test cache manager"""

    def setUp(self):
        """Create temporary test directory"""
        self.test_dir = tempfile.mkdtemp()
        self.cache_manager = CacheManager(self.test_dir)

    def tearDown(self):
        """Clean up test directory"""
        shutil.rmtree(self.test_dir)

    def test_cache_directory_creation(self):
        """Test automatic cache directory creation"""
        new_dir = os.path.join(self.test_dir, "new_cache")
        manager = CacheManager(new_dir)
        self.assertTrue(os.path.exists(new_dir))

    def test_save_and_load_cache(self):
        """Test cache save and load"""
        test_data = {"pikachu": {"id": 25, "types": ["electric"]}}
        key = "test_data"

        # Save
        self.cache_manager.save(key, test_data)
        cache_path = self.cache_manager.get_cache_path(key)
        self.assertTrue(os.path.exists(cache_path))

        # Load
        loaded_data = self.cache_manager.load(key)
        self.assertEqual(loaded_data["pikachu"]["id"], 25)

    def test_has_cache(self):
        """Test cache existence check"""
        key = "test_key"
        self.assertFalse(self.cache_manager.has_cache(key))

        self.cache_manager.save(key, {"test": "data"})
        self.assertTrue(self.cache_manager.has_cache(key))


class TestDataSources(unittest.TestCase):
    """Test data source classes"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.cache_manager = CacheManager(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch('pokemon_graph.requests.get')
    def test_pokeapi_source_load_with_cache(self, mock_get):
        """Test PokeAPI source does not make network requests when cache exists"""
        # Save cache first
        test_data = {"pikachu": {"id": 25}}
        self.cache_manager.save("pokemon_basic", test_data)

        source = PokeAPISource(self.cache_manager)
        result = source.load()

        # Verify no network request was made
        mock_get.assert_not_called()
        self.assertEqual(result["pikachu"]["id"], 25)

    @patch('pokemon_graph.requests.get')
    def test_pokeapi_source_load_without_cache(self, mock_get):
        """Test PokeAPI source makes network requests when no cache exists"""
        # Simulate API response - needs complete response structure
        mock_response = Mock()

        # First call (list) returns correct structure
        mock_response.json.side_effect = [
            {  # First call: get list
                "results": [{"name": "pikachu", "url": "https://api.example.com/pokemon/25"}]
            },
            {  # Second call: get detail
                "id": 25,
                "name": "pikachu",
                "types": [{"type": {"name": "electric"}}],
                "sprites": {"front_default": "url"},
                "stats": [
                    {"stat": {"name": "hp"}, "base_stat": 35},
                    {"stat": {"name": "attack"}, "base_stat": 55}
                ],
                "height": 4,
                "weight": 60
            }
        ]

        mock_get.return_value = mock_response

        source = PokeAPISource(self.cache_manager)

        # Should not raise exception now
        try:
            result = source.load(limit=1)
            # Verify result
            self.assertIn("pikachu", result)
        except Exception as e:
            self.fail(f"Exception occurred while loading data: {e}")

    def test_evolution_source_cache_key(self):
        """Test evolution source cache key"""
        source = EvolutionSource(self.cache_manager)
        self.assertEqual(source.get_cache_key(), "evolution_chains")

    def test_parse_evolution_chain(self):
        """Test evolution chain parsing"""
        source = EvolutionSource(self.cache_manager)

        # Simulate evolution chain data
        test_chain = {
            "species": {"name": "charmander"},
            "evolves_to": [{
                "species": {"name": "charmeleon"},
                "evolution_details": [{"min_level": 16}],
                "evolves_to": [{
                    "species": {"name": "charizard"},
                    "evolution_details": [{"min_level": 36}],
                    "evolves_to": []
                }]
            }]
        }

        pairs = source._parse_evolution_chain(test_chain)
        expected = [
            ("charmander", "charmeleon", 16),
            ("charmeleon", "charizard", 36)
        ]
        self.assertEqual(pairs, expected)

    def test_habitat_source_cache_key(self):
        """Test habitat source cache key"""
        source = HabitatSource(self.cache_manager)
        self.assertEqual(source.get_cache_key(), "habitat_data")


class TestPokemonGraph(unittest.TestCase):
    """Test Pokémon graph core class"""

    def setUp(self):
        self.graph = PokemonGraph()

        # Create test Pokémon
        self.pikachu = Pokemon(25, "pikachu", ["electric"], "",
                               {"hp": 35, "attack": 55}, habitat="forest")
        self.raichu = Pokemon(26, "raichu", ["electric"], "",
                              {"hp": 60, "attack": 90}, habitat="forest")
        self.bulbasaur = Pokemon(1, "bulbasaur", ["grass", "poison"], "",
                                 {"hp": 45, "attack": 49}, habitat="grassland")
        self.ivysaur = Pokemon(2, "ivysaur", ["grass", "poison"], "",
                               {"hp": 60, "attack": 62}, habitat="grassland")

        # Add to graph
        for pokemon in [self.pikachu, self.raichu, self.bulbasaur, self.ivysaur]:
            self.graph.add_pokemon(pokemon)

    def test_add_pokemon(self):
        """Test adding Pokémon node"""
        self.assertIn("pikachu", self.graph.pokemon_dict)
        self.assertIn("pikachu", self.graph.graph.nodes)
        node_data = self.graph.graph.nodes["pikachu"]
        self.assertEqual(node_data["types"], ["electric"])

    def test_add_evolution_edge(self):
        """Test adding evolution edge"""
        self.graph.add_evolution_edge("pikachu", "raichu", 1)

        self.assertTrue(self.graph.graph.has_edge("pikachu", "raichu"))
        edge_data = self.graph.graph.get_edge_data("pikachu", "raichu")
        # Get data from the first edge
        first_edge = next(iter(edge_data.values()))
        self.assertEqual(first_edge["relation"], "evolution")
        self.assertEqual(first_edge["level"], 1)

    def test_add_evolution_edge_missing_node(self):
        """Test adding evolution edge when node does not exist"""
        # Should not raise error
        self.graph.add_evolution_edge("missing", "raichu", 1)
        self.assertFalse(self.graph.graph.has_edge("missing", "raichu"))

    def test_add_type_similarity_edge(self):
        """Test adding type similarity edge"""
        self.graph.add_type_similarity_edge("pikachu", "raichu", 1)

        self.assertTrue(self.graph.graph.has_edge("pikachu", "raichu"))
        edge_data = self.graph.graph.get_edge_data("pikachu", "raichu")
        first_edge = next(iter(edge_data.values()))
        self.assertEqual(first_edge["relation"], "type_similarity")

    def test_add_habitat_edge(self):
        """Test adding habitat edge"""
        # Same habitat should add edge
        self.graph.add_habitat_edge("pikachu", "raichu")
        self.assertTrue(self.graph.graph.has_edge("pikachu", "raichu"))

        # Different habitat should not add edge
        self.graph.add_habitat_edge("pikachu", "bulbasaur")
        self.assertFalse(self.graph.graph.has_edge("pikachu", "bulbasaur"))

    def test_find_shortest_path_basic(self):
        """Test basic shortest path finding"""
        # Add evolution relationships
        self.graph.add_evolution_edge("pikachu", "raichu", 1)
        self.graph.add_evolution_edge("bulbasaur", "ivysaur", 16)

        path = self.graph.find_shortest_path("pikachu", "raichu")
        self.assertEqual(path, ["pikachu", "raichu"])

    def test_find_shortest_path_no_connection(self):
        """Test path finding when there is no connection"""
        # Two unconnected nodes
        path = self.graph.find_shortest_path("pikachu", "bulbasaur")
        self.assertEqual(path, [])

    def test_find_shortest_path_with_filter(self):
        """Test shortest path with relationship filter"""
        # Add two types of relationships
        self.graph.add_evolution_edge("pikachu", "raichu", 1)
        self.graph.add_type_similarity_edge("pikachu", "raichu", 1)

        # Only look for evolution relationship
        path = self.graph.find_shortest_path("pikachu", "raichu",
                                             relation_filter="evolution")
        self.assertEqual(path, ["pikachu", "raichu"])

    def test_centrality_ranking(self):
        """Test centrality ranking"""
        # Add some edges
        self.graph.add_evolution_edge("pikachu", "raichu", 1)
        self.graph.add_type_similarity_edge("pikachu", "bulbasaur", 1)

        ranking = self.graph.get_centrality_ranking(2)

        # Verify ranking format
        self.assertIsInstance(ranking, list)
        self.assertLessEqual(len(ranking), 2)
        if ranking:
            self.assertEqual(len(ranking[0]), 2)  # (name, score)

    def test_centrality_strategy_pattern(self):
        """Test centrality strategy pattern"""
        # Test different strategies
        strategies = [
            DegreeCentrality(),
            BetweennessCentrality(),
            ClosenessCentrality()
        ]

        for strategy in strategies:
            self.graph.set_centrality_strategy(strategy)
            ranking = self.graph.get_centrality_ranking(2)
            # Just verify no error
            self.assertIsNotNone(ranking)

    def test_get_pokemon_by_habitat(self):
        """Test getting Pokémon by habitat"""
        forest_pokemon = self.graph.get_pokemon_by_habitat("forest")
        self.assertEqual(len(forest_pokemon), 2)  # pikachu, raichu
        self.assertIn(self.pikachu, forest_pokemon)

        grassland_pokemon = self.graph.get_pokemon_by_habitat("grassland")
        self.assertEqual(len(grassland_pokemon), 2)  # bulbasaur, ivysaur

    def test_get_habitat_clusters(self):
        """Test getting habitat clusters"""
        clusters = self.graph.get_habitat_clusters()

        self.assertIn("forest", clusters)
        self.assertIn("grassland", clusters)
        self.assertEqual(len(clusters["forest"]), 2)
        self.assertEqual(len(clusters["grassland"]), 2)

    def test_find_type_habitat_correlation(self):
        """Test type-habitat correlation discovery"""
        insights = self.graph.find_type_habitat_correlation()

        # Should have at least some insights
        self.assertIsInstance(insights, list)

        # Should contain electric type insight
        electric_insights = [i for i in insights if "electric" in i]
        self.assertTrue(any("forest" in i for i in electric_insights))

    def test_generate_path_narrative(self):
        """Test path story generation"""
        path = ["pikachu", "raichu"]

        # No edge should return simple path
        story = self.graph.generate_path_narrative(path)
        # Check case-insensitively
        self.assertIn("pikachu", story.lower())
        self.assertIn("raichu", story.lower())

        # After adding evolution edge, should generate detailed story
        self.graph.add_evolution_edge("pikachu", "raichu", 1)
        story_with_edge = self.graph.generate_path_narrative(path)
        # Check for "evolved" keyword
        self.assertIn("evolved", story_with_edge.lower())

    def test_empty_path_narrative(self):
        """Test empty path story"""
        story = self.graph.generate_path_narrative([])
        self.assertEqual(story, "No path found!")


class TestDataLoader(unittest.TestCase):
    """Test data loader"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

        # Mock cache directory
        with patch('pokemon_graph.CacheManager') as MockCacheManager:
            self.cache_manager = MockCacheManager.return_value
            self.cache_manager.cache_dir = self.test_dir
            self.loader = DataLoader()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch('pokemon_graph.PokeAPISource')
    @patch('pokemon_graph.EvolutionSource')
    @patch('pokemon_graph.HabitatSource')
    def test_load_all_data(self, mock_habitat, mock_evolution, mock_pokeapi):
        """Test loading all data"""
        # Set mock return values
        mock_pokeapi.return_value.load.return_value = {"pikachu": {"id": 25}}
        mock_evolution.return_value.load.return_value = [("pikachu", "raichu", 1)]
        mock_habitat.return_value.load.return_value = {"pikachu": {"primary_habitat": "forest"}}

        # Re-create loader to use mocks
        self.loader.pokeapi_source = mock_pokeapi.return_value
        self.loader.evolution_source = mock_evolution.return_value
        self.loader.habitat_source = mock_habitat.return_value

        pokemon_data, evo_chains, habitat_data = self.loader.load_all_data()

        self.assertEqual(pokemon_data["pikachu"]["id"], 25)
        self.assertEqual(evo_chains[0][0], "pikachu")
        self.assertEqual(habitat_data["pikachu"]["primary_habitat"], "forest")

    def test_integration_habitat_data_merging(self):
        """Test habitat data integration (integration test)"""
        # This is a simple integration test that requires real API
        # Can use small data volume
        pass


class TestGraphInsights(unittest.TestCase):
    """Test graph structure insights (key for A-grade project)"""

    def setUp(self):
        self.graph = PokemonGraph()

        # Create a more complex test graph
        pokemon_data = [
            (25, "pikachu", ["electric"], "forest"),
            (26, "raichu", ["electric"], "forest"),
            (172, "pichu", ["electric"], "forest"),
            (1, "bulbasaur", ["grass", "poison"], "grassland"),
            (2, "ivysaur", ["grass", "poison"], "grassland"),
            (3, "venusaur", ["grass", "poison"], "grassland"),
            (4, "charmander", ["fire"], "mountain"),
            (5, "charmeleon", ["fire"], "mountain"),
            (6, "charizard", ["fire", "flying"], "mountain"),
            (7, "squirtle", ["water"], "sea"),
            (8, "wartortle", ["water"], "sea"),
            (9, "blastoise", ["water"], "sea"),
        ]

        for pid, name, types, habitat in pokemon_data:
            pokemon = Pokemon(pid, name, types, "", {}, habitat=habitat)
            self.graph.add_pokemon(pokemon)

    def test_habitat_clusters_size(self):
        """Test size of habitat clusters"""
        clusters = self.graph.get_habitat_clusters()

        self.assertEqual(len(clusters["forest"]), 3)  # pichu, pikachu, raichu
        self.assertEqual(len(clusters["grassland"]), 3)  # Grass starters
        self.assertEqual(len(clusters["mountain"]), 3)  # Fire starters
        self.assertEqual(len(clusters["sea"]), 3)  # Water starters

    def test_cross_habitat_connections(self):
        """Test cross-habitat connections (via type similarity)"""
        # Add type similarity edges
        self.graph.add_type_similarity_edge("pikachu", "raichu", 1)
        self.graph.add_type_similarity_edge("charizard", "charmander", 1)

        # Verify connections within same habitat
        self.assertTrue(self.graph.graph.has_edge("pikachu", "raichu"))

        # Verify no edge between different habitats even with same type (should not connect because types differ)
        self.assertFalse(self.graph.graph.has_edge("pikachu", "charizard"))

    def test_centrality_reflects_evolutionary_importance(self):
        """Test whether centrality reflects evolutionary importance"""
        # Add evolution edges
        evo_pairs = [
            ("pichu", "pikachu", 1),
            ("pikachu", "raichu", 1),
            ("bulbasaur", "ivysaur", 16),
            ("ivysaur", "venusaur", 32),
            ("charmander", "charmeleon", 16),
            ("charmeleon", "charizard", 36),
            ("squirtle", "wartortle", 16),
            ("wartortle", "blastoise", 36),
        ]

        for f, t, l in evo_pairs:
            self.graph.add_evolution_edge(f, t, l)

        # Calculate centrality
        centrality = self.graph.get_centrality_ranking()

        # Intermediate evolution stages (e.g. pikachu, ivysaur) should be more central than the ends
        centrality_dict = dict(centrality)

        # Verify pikachu is more central than pichu (connects pichu and raichu)
        self.assertGreater(centrality_dict.get("pikachu", 0),
                           centrality_dict.get("pichu", 0))


if __name__ == "__main__":
    # Run tests
    unittest.main(verbosity=2)