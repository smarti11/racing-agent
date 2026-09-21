/**
 * Passi di Firenze — classic historic-center loop (~2.5–3 km, ~2 hours with stops).
 * Coordinates are WGS84; unlockRadiusMeters is generous for GPS drift in narrow streets.
 */
window.TOUR = {
  id: "passi-di-firenze-v1",
  brand: "Passi",
  title: "Passi di Firenze",
  tagline: "A walking audio tour of Florence’s historic heart.",
  durationLabel: "About 2 hours · 8 stops",
  distanceLabel: "~3 km loop",
  startHint: "Begin at the steps of the Duomo. Allow location access, or use “I’m here” to unlock each stop while testing.",
  unlockRadiusMeters: 90,
  mapCenter: [43.7711, 11.2532],
  mapZoom: 15,
  stops: [
    {
      id: "duomo",
      order: 1,
      name: "Piazza del Duomo",
      shortName: "Duomo",
      lat: 43.7731,
      lng: 11.256,
      walkFromPrev: "Start here — the marble façade faces you.",
      audio: "audio/01-duomo.wav",
      durationSec: 18,
      script: [
        "Welcome to Florence. You are standing in Piazza del Duomo, the religious and civic heartbeat of the city for seven centuries.",
        "Look up at Santa Maria del Fiore — the cathedral Brunelleschi crowned with that impossible brick dome. In 1420 no one knew how to span that space without scaffolding. He engineered a double shell, herringbone brickwork, and a lantern that still steadies the skyline.",
        "Giotto’s campanile rises beside you in white, green, and pink marble. Climb it later if your legs allow — the view back across the dome is worth every step.",
        "When you are ready, walk a few meters toward the octagonal baptistery in front of the cathedral. That is your next stop."
      ]
    },
    {
      id: "baptistery",
      order: 2,
      name: "Battistero di San Giovanni",
      shortName: "Baptistery",
      lat: 43.7735,
      lng: 11.2549,
      walkFromPrev: "Cross the square to the octagonal baptistery facing the Duomo.",
      audio: "audio/02-baptistery.wav",
      durationSec: 16,
      script: [
        "The Baptistery of San Giovanni is older than the cathedral behind you — its green-and-white marble geometry has stood here since the Middle Ages, and Florentines once believed it began as a Roman temple.",
        "Find the eastern doors — Ghiberti’s Gates of Paradise. Michelangelo gave them that name. Each panel is a compressed Bible in bronze: perspective, narrative, and light trapped in metal.",
        "Dante was baptized here. So were generations of Medici. This small octagon held the city’s spiritual identity long before the dome stole the postcard.",
        "Leave the square south along Via dei Calzaiuoli, the old processional street toward the civic center."
      ]
    },
    {
      id: "repubblica",
      order: 3,
      name: "Piazza della Repubblica",
      shortName: "Repubblica",
      lat: 43.7714,
      lng: 11.254,
      walkFromPrev: "Walk south on Via dei Calzaiuoli into the open square.",
      audio: "audio/03-repubblica.wav",
      durationSec: 14,
      script: [
        "Piazza della Repubblica sits on the site of the ancient Roman forum — Florence’s first marketplace. The grand triumphal arch and cafés you see today are nineteenth-century reinventions after the medieval ghetto was cleared.",
        "Pause under the colonnades. This is where the city’s layers stack: Roman grid, medieval lanes, Risorgimento pride. The carousel turns where merchants once argued over cloth and coin.",
        "Look for the inscription on the arch celebrating the square as the center of the city. For walkers, it is still a useful pivot — four directions of Florence peel away from here.",
        "Continue south a short stretch and duck left toward Orsanmichele, the grain-hall-turned-church on Via Calzaiuoli’s side streets."
      ]
    },
    {
      id: "orsanmichele",
      order: 4,
      name: "Orsanmichele",
      shortName: "Orsanmichele",
      lat: 43.7707,
      lng: 11.2549,
      walkFromPrev: "From Repubblica, continue toward Via dei Calzaiuoli / Via dell’Arte della Lana.",
      audio: "audio/04-orsanmichele.wav",
      durationSec: 15,
      script: [
        "Orsanmichele began as an open grain market. When a painted Madonna drew pilgrims, the guilds enclosed it into a church — still stacked like a warehouse of miracles.",
        "Circle the exterior niches. Each major guild commissioned a saint: Ghiberti, Donatello, Verrocchio. These bronzes and marbles were civic advertising as much as devotion — Florence’s middle class writing itself into stone.",
        "If the doors are open, step inside for the tabernacle and the cool quiet. Outside, notice how the building fills the block: this is guild Florence, practical and devout in the same breath.",
        "Walk on toward Piazza della Signoria — the political stage of the Republic."
      ]
    },
    {
      id: "signoria",
      order: 5,
      name: "Piazza della Signoria",
      shortName: "Signoria",
      lat: 43.7696,
      lng: 11.2555,
      walkFromPrev: "Continue south into the wide civic square.",
      audio: "audio/05-signoria.wav",
      durationSec: 20,
      script: [
        "Piazza della Signoria is Florence without soft edges. Palazzo Vecchio’s fortress tower still watches the square where the Republic debated, Medici ruled, and Savonarola burned.",
        "Face the palace. A copy of Michelangelo’s David stands where the original once guarded the doorway — a republican emblem of defiant youth. Neptune’s fountain and Cellini’s Perseus nearby remind you this was also a Medici outdoor gallery.",
        "Under the Loggia dei Lanzi, sculptures stand in open air like an unfinished conversation between myth and power. Tourists pose; the stone keeps older scores.",
        "When you leave, pass the Uffizi’s narrow courtyard toward the river — the Vasari corridor once let rulers walk above the crowd to the Ponte Vecchio."
      ]
    },
    {
      id: "ponte-vecchio",
      order: 6,
      name: "Ponte Vecchio",
      shortName: "Ponte Vecchio",
      lat: 43.7679,
      lng: 11.2531,
      walkFromPrev: "Through the Uffizi courtyard to the Arno, then onto the bridge.",
      audio: "audio/06-ponte-vecchio.wav",
      durationSec: 17,
      script: [
        "The Ponte Vecchio has spanned the Arno since 1345, shops clinging to its sides like barnacles. Butchers worked here first; the Medici replaced them with goldsmiths so the corridor above would smell of metal, not meat.",
        "Walk to mid-span and look both ways along the river. Upstream and down, Florence folds into ochre walls and green shutters. Floods have tested this bridge; it alone survived 1944 when others were destroyed.",
        "The Vasari Corridor runs above the eastern shops — a private skyway from Palazzo Vecchio to Palazzo Pitti. Power preferred not to touch the street.",
        "Cross fully into the Oltrarno. Your next stop is just beyond the bridge, on the quieter south bank."
      ]
    },
    {
      id: "oltrarno",
      order: 7,
      name: "Oltrarno — Via Guicciardini",
      shortName: "Oltrarno",
      lat: 43.7665,
      lng: 11.2518,
      walkFromPrev: "Finish crossing Ponte Vecchio; pause on Via Guicciardini toward Palazzo Pitti.",
      audio: "audio/07-oltrarno.wav",
      durationSec: 18,
      script: [
        "You are now in the Oltrarno — literally ‘beyond the Arno.’ This bank feels more lived-in: workshops, neighborhood trattorie, laundry lines, the hum of a Florence that is not only a museum.",
        "Ahead, Palazzo Pitti spreads like a stone cliff. The Medici bought it and made it their grand residence; the Boboli Gardens climb the hill behind. Even if you skip the ticket lines today, notice how the palace turns its back on the river and claims the slope.",
        "Artisans still work leather and wood a few streets west toward Santo Spirito. If you have time after the tour, wander there for a slower Florence.",
        "Retrace to the bridge, cross back, and bear east along the north bank toward the great Franciscan church of Santa Croce."
      ]
    },
    {
      id: "santa-croce",
      order: 8,
      name: "Piazza Santa Croce",
      shortName: "Santa Croce",
      lat: 43.7687,
      lng: 11.262,
      walkFromPrev: "Recross Ponte Vecchio, then east via Por Santa Maria / Via dei Neri toward Santa Croce.",
      audio: "audio/08-santa-croce.wav",
      durationSec: 19,
      script: [
        "Piazza Santa Croce opens wide before the Franciscan basilica — Florence’s pantheon. Inside rest Michelangelo, Galileo, Machiavelli, Rossini; outside, the façade’s Star of David recalls architect Matas and the square’s long civic life.",
        "This piazza has hosted tournaments, sermons, and the Calcio Storico — a violent Renaissance football still played in June on sand dumped over these stones.",
        "Stand with your back to the church and look west. You have walked a loop through faith, guild, republic, river, and memory. The dome you started beneath still punctures the skyline if you know where to glance.",
        "Your tour ends here. Rest on the steps, find a gelato, or step inside Santa Croce when the light is soft. Grazie for walking with Passi — Florence rewards those who move at the city’s own pace."
      ]
    }
  ]
};
