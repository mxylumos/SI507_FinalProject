import streamlit as st
import pandas as pd
from pokemon_graph import Pokemon, PokemonGraph, DataLoader, CacheManager
import networkx as nx
import time

st.set_page_config(page_title="Pokémon Network Explorer", layout="wide")
st.title("Pokémon Evolution & Type Network")
st.markdown("**SI 507 Final Project** — Graph + OOP + Real API + Streamlit + Habitat Insights")


# ==================== Data Loading ====================
@st.cache_resource
def init_graph():
    """Initialize graph data - using the new DataLoader interface"""
    loader = DataLoader()

    # Use the new load_all_data method
    pokemon_data, evo_chains, habitat_data = loader.load_all_data(limit=151)

    graph = PokemonGraph()

    # Add Pokémon nodes
    for name, info in pokemon_data.items():
        p = Pokemon(
            id=info["id"],
            name=name,
            types=info["types"],
            sprite=info["sprite"],
            stats=info["stats"],
            habitat=info.get("habitat"),  # From the second data source
            color=info.get("color"),
            height=info.get("height"),
            weight=info.get("weight")
        )
        graph.add_pokemon(p)

    # Add evolution edges
    for from_name, to_name, level in evo_chains:
        graph.add_evolution_edge(from_name, to_name, level)

    # Add type similarity edges (clustering insight)
    names = list(pokemon_data.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            p1 = graph.pokemon_dict[names[i]]
            p2 = graph.pokemon_dict[names[j]]
            shared = len(set(p1.types) & set(p2.types))
            if shared > 0:
                graph.add_type_similarity_edge(names[i], names[j], shared)

    # Add habitat similarity edges (insight from the second data source)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            graph.add_habitat_edge(names[i], names[j])

    return graph


# Initialize graph
with st.spinner("Loading Pokémon data... First run requires download, please wait patiently..."):
    graph = init_graph()

# ==================== Sidebar ====================
with st.sidebar:
    st.header("📘 About This Project")
    st.markdown("""
    **Graph Structure Insights:**
    - 🟢 **Evolution edges**: Pokémon evolution relationships
    - 🔵 **Type edges**: Connections sharing the same type
    - 🟤 **Habitat edges**: Connections in the same habitat

    **Data Sources:**
    - PokéAPI (basic data + evolution)
    - PokéAPI (habitat data) - second data source
    """)

    st.header("🎯 Today's Insights")
    if st.button("Discover New Insights"):
        insights = graph.find_type_habitat_correlation()
        for insight in insights[:3]:
            st.info(insight)

    st.header("⚙️ Centrality Strategy")
    strategy = st.selectbox(
        "Select Centrality Algorithm",
        ["Degree Centrality", "Betweenness Centrality", "Closeness Centrality"]
    )

    if strategy == "Degree Centrality":
        from pokemon_graph import DegreeCentrality

        graph.set_centrality_strategy(DegreeCentrality())
    elif strategy == "Betweenness Centrality":
        from pokemon_graph import BetweennessCentrality

        graph.set_centrality_strategy(BetweennessCentrality())
    else:
        from pokemon_graph import ClosenessCentrality

        graph.set_centrality_strategy(ClosenessCentrality())

# ==================== 5 Interaction Modes ====================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🔍 Search Query", "📊 Pokémon Details", "🛤️ Shortest Path",
    "🏆 Centrality Ranking", "🌳 Habitat Insights"
])

with tab1:
    st.header("🔍 Search Pokémon")
    search = st.text_input("Enter Pokémon name (English)", "pikachu").lower().strip()

    if search:
        if search in graph.pokemon_dict:
            p = graph.pokemon_dict[search]
            col1, col2 = st.columns([1, 2])
            with col1:
                if p.sprite:
                    st.image(p.sprite, width=150)
                else:
                    st.info("No image")
            with col2:
                st.subheader(p.name.capitalize())
                st.write(f"**ID**: {p.id}")
                st.write(f"**Types**: {', '.join(p.types)}")
                st.write(f"**Habitat**: {p.habitat or 'Unknown'}")
                st.write(f"**Color**: {p.color or 'Unknown'}")

                # Display stats
                st.write("**Base Stats**:")
                stats_df = pd.DataFrame(
                    [p.stats.values()],
                    columns=p.stats.keys(),
                    index=[p.name.capitalize()]
                )
                st.dataframe(stats_df)
        else:
            st.warning(f"Pokémon not found: {search}")
            st.info("Try: pikachu, charizard, bulbasaur, mewtwo")

with tab2:
    st.header("📊 Pokémon Details Browser")
    name = st.selectbox("Select Pokémon", sorted(list(graph.pokemon_dict.keys())))

    if name:
        p = graph.pokemon_dict[name]

        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            if p.sprite:
                st.image(p.sprite, width=200)

        with col2:
            st.subheader(f"{p.name.capitalize()} #{p.id}")

            # Type badges
            type_badges = " ".join([f"🏷️ {t}" for t in p.types])
            st.markdown(f"**Types**: {type_badges}")

            # Habitat information
            st.markdown(f"**Habitat**: {p.habitat or 'Unknown'}")
            st.markdown(f"**Color**: {p.color or 'Unknown'}")

            if p.height:
                st.markdown(f"**Height**: {p.height / 10:.1f} m")
            if p.weight:
                st.markdown(f"**Weight**: {p.weight / 10:.1f} kg")

        with col3:
            st.markdown("**Base Stats Bar Chart**")
            # Simple bar chart
            stats_df = pd.DataFrame(
                [p.stats.values()],
                columns=p.stats.keys(),
                index=[p.name.capitalize()]
            ).T
            st.bar_chart(stats_df)

        # Display neighbors (connected Pokémon)
        st.subheader("🔗 Network Connections")
        neighbors = list(graph.graph.neighbors(name))
        if neighbors:
            cols = st.columns(4)
            for i, neighbor in enumerate(neighbors[:8]):  # Show at most 8
                if i < len(cols):
                    with cols[i % 4]:
                        neighbor_p = graph.pokemon_dict.get(neighbor)
                        if neighbor_p and neighbor_p.sprite:
                            st.image(neighbor_p.sprite, width=80)
                        st.caption(neighbor.capitalize())
        else:
            st.info("This Pokémon has no connections to other Pokémon")

with tab3:
    st.header("🛤️ Find Shortest Path")
    st.markdown("Discover the connection path between any two Pokémon")

    col1, col2 = st.columns(2)

    pokemon_list = sorted(list(graph.pokemon_dict.keys()))

    start = col1.selectbox("Start", pokemon_list,
                           index=pokemon_list.index("pikachu") if "pikachu" in pokemon_list else 0)
    end = col2.selectbox("End", pokemon_list,
                         index=pokemon_list.index("raichu") if "raichu" in pokemon_list else min(1,
                                                                                                 len(pokemon_list) - 1))

    # Relationship filter options
    relation_filter = st.radio(
        "Relationship Type Filter",
        ["All Relationships", "Evolution Only", "Type Similarity Only", "Same Habitat Only"]
    )

    filter_map = {
        "All Relationships": None,
        "Evolution Only": "evolution",
        "Type Similarity Only": "type_similarity",
        "Same Habitat Only": "same_habitat"
    }

    if st.button("🔍 Find Path"):
        with st.spinner("Calculating..."):
            path = graph.find_shortest_path(
                start, end,
                relation_filter=filter_map[relation_filter]
            )

        if path:
            st.success(f"Path found! {len(path)} steps")

            # Display path
            path_str = " → ".join([p.capitalize() for p in path])
            st.markdown(f"**Path**: {path_str}")

            # Generate story
            story = graph.generate_path_narrative(path)
            st.markdown(story)

            # Display Pokémon images along the path
            st.subheader("Pokémon on the Path")
            cols = st.columns(len(path))
            for i, p_name in enumerate(path):
                with cols[i]:
                    p = graph.pokemon_dict.get(p_name)
                    if p and p.sprite:
                        st.image(p.sprite, width=80)
                    st.caption(p_name.capitalize())
        else:
            st.error("No connecting path found")

with tab4:
    st.header("🏆 Centrality Ranking")
    st.markdown("Who is the Kevin Bacon of the Pokémon world?")

    top_n = st.slider("Show Top N", 5, 20, 10)

    if st.button("Calculate Centrality Ranking"):
        ranking = graph.get_centrality_ranking(top_n)

        # Create DataFrame
        df = pd.DataFrame(ranking, columns=["Pokémon", "Centrality Score"])

        # Add type and habitat information
        df["Types"] = df["Pokémon"].apply(
            lambda x: ", ".join(graph.pokemon_dict[x].types) if x in graph.pokemon_dict else ""
        )
        df["Habitat"] = df["Pokémon"].apply(
            lambda x: graph.pokemon_dict[x].habitat if x in graph.pokemon_dict else ""
        )

        # Format score
        df["Centrality Score"] = df["Centrality Score"].apply(lambda x: f"{x:.4f}")

        st.dataframe(df, use_container_width=True)

        # Display top Pokémon images
        st.subheader(f"Top {min(5, top_n)} Pokémon")
        cols = st.columns(5)
        for i, (name, score) in enumerate(ranking[:5]):
            with cols[i]:
                p = graph.pokemon_dict.get(name)
                if p and p.sprite:
                    st.image(p.sprite, width=100)
                st.caption(f"{name.capitalize()}")
                st.caption(f"Score: {float(score):.3f}")

with tab5:
    st.header("🌳 Habitat Insights")
    st.markdown("**Graph structure insights based on the second data source**")

    # Get habitat clusters
    clusters = graph.get_habitat_clusters()

    if clusters:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Habitat Distribution")
            habitat_counts = {h: len(p) for h, p in clusters.items() if h}
            if habitat_counts:
                df_habitat = pd.DataFrame(
                    habitat_counts.items(),
                    columns=["Habitat", "Pokémon Count"]
                )
                st.bar_chart(df_habitat.set_index("Habitat"))
            else:
                st.info("No habitat data")

        with col2:
            st.subheader("Type-Habitat Correlation")
            insights = graph.find_type_habitat_correlation()
            if insights:
                for insight in insights:
                    st.info(insight)
            else:
                st.info("No insights available yet")

        # Select habitat to view Pokémon
        st.subheader("Filter by Habitat")

        # Filter out None values
        valid_habitats = [h for h in clusters.keys() if h]
        if valid_habitats:
            selected_habitat = st.selectbox(
                "Select Habitat",
                valid_habitats
            )

            if selected_habitat:
                pokemon_list = graph.get_pokemon_by_habitat(selected_habitat)

                st.write(f"Found {len(pokemon_list)} Pokémon living in {selected_habitat}")

                # Display Pokémon grid for this habitat
                cols = st.columns(4)
                for i, pokemon in enumerate(pokemon_list[:12]):  # Show at most 12
                    with cols[i % 4]:
                        if pokemon.sprite:
                            st.image(pokemon.sprite, width=100)
                        else:
                            st.markdown(f"**{pokemon.name.capitalize()}**")

                        # Display type badges
                        type_badges = " ".join([f"🎨 {t}" for t in pokemon.types])
                        st.markdown(f"<small>{type_badges}</small>",
                                    unsafe_allow_html=True)
        else:
            st.warning("No habitat data found")
    else:
        st.warning("Habitat data is loading...")

# ==================== Graph Visualization ====================
st.header("🕸️ Full Network Graph")
if st.checkbox("Show Full Network Graph"):
    try:
        from pyvis.network import Network

        # Create network
        net = Network(height="600px", width="100%", directed=True, bgcolor="#ffffff", font_color="black")

        # Add nodes
        for node_name, node_data in graph.graph.nodes(data=True):
            p = graph.pokemon_dict.get(node_name)
            if p:
                # Set color by type
                if "fire" in p.types:
                    color = "#FF4444"
                elif "water" in p.types:
                    color = "#4444FF"
                elif "grass" in p.types:
                    color = "#44FF44"
                elif "electric" in p.types:
                    color = "#FFFF44"
                elif "psychic" in p.types:
                    color = "#FF44FF"
                else:
                    color = "#AAAAAA"

                title = f"{p.name.capitalize()}<br>Types: {', '.join(p.types)}<br>Habitat: {p.habitat or 'Unknown'}"

                net.add_node(
                    node_name,
                    label=node_name.capitalize(),
                    color=color,
                    title=title,
                    size=20
                )

        # Add edges
        for u, v, k, data in graph.graph.edges(keys=True, data=True):
            relation = data.get('relation', 'unknown')

            # Set edge color by relationship
            if relation == 'evolution':
                color = '#00AA00'
                width = 3
            elif relation == 'type_similarity':
                color = '#0000AA'
                width = 1
            elif relation == 'same_habitat':
                color = '#AA5500'
                width = 2
            else:
                color = '#AAAAAA'
                width = 1

            net.add_edge(u, v, color=color, width=width, title=relation)

        # Save and display
        net.save_graph("pokemon_network.html")

        with open("pokemon_network.html", "r", encoding="utf-8") as f:
            html_content = f.read()

        st.components.v1.html(html_content, height=700)

    except Exception as e:
        st.error(f"Visualization error: {e}")
        st.info("Please install pyvis first: pip install pyvis")

# ==================== Test Suite Information ====================
with st.expander("🧪 Test Suite Information"):
    st.markdown("""
    ### Test Coverage
    - ✅ **Pokemon class**: Creation, property calculation, type handling
    - ✅ **CacheManager**: Cache save/load
    - ✅ **Data sources**: API calls, caching mechanism
    - ✅ **Graph operations**: Add nodes/edges, path finding
    - ✅ **Centrality**: Multiple strategy modes
    - ✅ **Habitat insights**: Cluster analysis, correlation discovery

    ### Run Tests
    ```bash
    python -m pytest test_pokemon_graph.py -v
""")