import { View, Text, FlatList, TouchableOpacity, StyleSheet } from "react-native";
import { trpc } from "./_layout";
import { Link } from "expo-router";

export default function DiscoverScreen() {
  const { data, isLoading } = trpc.catalog.discover.useQuery({ limit: 10 });

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Discover</Text>
      <Text style={styles.subtitle}>Curated food, not the algorithm</Text>
      {isLoading && <Text>Loading...</Text>}

      <Text style={styles.section}>Featured Creators</Text>
      <FlatList
        data={data?.featuredCreators ?? []}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <Link href={`/creator/${item.handle}`} asChild>
            <TouchableOpacity style={styles.card}>
              <Text style={styles.cardTitle}>{item.name}</Text>
              <Text style={styles.cardSub}>@{item.handle}</Text>
              <Text style={styles.cardMeta}>
                {item._count.followers} followers · {item._count.creatorProducts} picks
              </Text>
            </TouchableOpacity>
          </Link>
        )}
      />

      <Text style={styles.section}>Trending Products</Text>
      <FlatList
        data={data?.trendingProducts ?? []}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>{item.name}</Text>
            {item.brand && <Text style={styles.cardSub}>{item.brand}</Text>}
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: "#fafaf9" },
  title: { fontSize: 28, fontWeight: "300", fontFamily: "Georgia", marginBottom: 4 },
  subtitle: { fontSize: 14, color: "#6b6b6b", marginBottom: 16 },
  section: { fontSize: 18, fontWeight: "600", marginTop: 16, marginBottom: 8 },
  card: {
    backgroundColor: "#fff",
    padding: 16,
    borderRadius: 12,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: "#e7e5e4",
  },
  cardTitle: { fontSize: 16, fontWeight: "600" },
  cardSub: { color: "#78716c", marginTop: 2 },
  cardMeta: { color: "#a8a29e", fontSize: 12, marginTop: 4 },
});
