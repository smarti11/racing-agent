/**
 * Passi di Firenze — historic-center loop with hillside viewpoint (~4 km, ~2.5 hours with stops).
 * Coordinates are WGS84; unlockRadiusMeters is generous for GPS drift in narrow streets.
 */
window.TOUR = {
  id: "passi-di-firenze-v6",
  brand: "Passi",
  title: "Passi di Firenze",
  tagline: "A walking audio tour of Florence’s historic heart.",
  durationLabel: "About 2.5 hours · 9 stops",
  distanceLabel: "~4 km loop",
  startHint: "Begin at the steps of the Duomo. Allow location access, or use “I’m here” to unlock each stop while testing.",
  unlockRadiusMeters: 90,
  mapCenter: [43.7685, 11.2575],
  mapZoom: 14,
  stops: [
    {
      id: "duomo",
      order: 1,
      name: "Piazza del Duomo",
      shortName: "Duomo",
      lat: 43.7731,
      lng: 11.256,
      walkFromPrev: "Start here — the marble façade faces you.",
      audio: "audio/01-duomo.mp3",
      durationSec: 167,
      script: [
        "Welcome to Florence. You are standing in Piazza del Duomo — for seven centuries the city’s religious and civic heart. The cathedral before you is Santa Maria del Fiore, Our Lady of the Flower.",
        "Who paid for this? Not a single king or pope. In 1296 the Commune of Florence — the republican city government — commissioned a new cathedral on the site of the older church of Santa Reparata. The first master builder was Arnolfo di Cambio. After his death the project stalled, then in 1331 the powerful Arte della Lana, the Wool Guild, took charge of the works board called the Opera del Duomo. Guild merchants, not princes, drove the budgets.",
        "Money came from public taxes and gabelle — city customs duties — with a fixed share steered to the Opera year after year. Offerings and bequests helped, but this was civic capitalism: Florence taxed trade so the skyline would preach Florentine greatness.",
        "Giotto was named master in 1334 and began the freestanding campanile beside you. Francesco Talenti later enlarged the plan into the vast Gothic shell you see. Then came the problem no one could solve: how to roof an octagon this wide without wooden centering that would collapse under its own weight.",
        "In 1418 the Opera held a competition. Filippo Brunelleschi won the commission for the dome. From 1420 to 1436 he raised a double-shell brick vault with herringbone courses and stone chains — still the largest masonry dome on Earth, about thirty-seven thousand tons and more than four million bricks. Pope Eugene the Fourth consecrated the cathedral in 1436. The marble façade you face is nineteenth-century; the engineering genius is Brunelleschi’s.",
        "What would this cost today? Medieval ledgers do not give one tidy total, but quantity-surveyor style rebuilds of comparable cathedrals land in the high hundreds of millions. A full modern reconstruction of Santa Maria del Fiore — marble cladding, sculpture, and that unrepeatable dome — is reasonably estimated at roughly seven hundred million to one billion euros, or about seven hundred fifty million to one point one billion US dollars. The dome alone would devour a huge share: specialized masonry, temporary works, and artisan labor at twenty-first-century rates.",
        "Climb the campanile or the dome later if you can. When you are ready, walk a few meters to the octagonal baptistery in front of the cathedral — your next stop, and another guild masterpiece."
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
      audio: "audio/02-baptistery.mp3",
      durationSec: 171,
      script: [
        "The Baptistery of San Giovanni is older than the cathedral behind you. Its green-and-white marble geometry is largely medieval, though Florentines long claimed a Roman temple stood here first. Dante was baptized inside. So were generations of Medici. This octagon was Florence’s spiritual identity card long before the dome stole the postcard.",
        "Who commissioned it and kept it gleaming? The Arte di Calimala — the Cloth Importers’ Guild, among the richest in Europe. By the late thirteen hundreds they were repairing columns and importing eastern marbles that cost far more than local Tuscan stone. The baptistery was their civic brag: we dress Europe in cloth, and we dress God’s house in marble.",
        "The doors are where the money and the genius meet. Andrea Pisano’s bronze south doors came first. Then, in 1401, the Calimala ran a famous competition for new doors — the contest that art historians often treat as the opening bell of the Renaissance. Young Lorenzo Ghiberti beat Brunelleschi. In 1403 the guild signed him; by Easter 1424 his first set was hung facing the cathedral. Ghiberti himself recorded a fee of about twenty-two thousand gold florins for that campaign.",
        "What is twenty-two thousand florins in today’s money? A florin held roughly three and a half grams of gold. Melt value alone is only a few million dollars — but that understates the project. Measured in labor purchasing power, scholars put one florin in the ballpark of several hundred modern dollars of unskilled work. On that yardstick, Ghiberti’s first doors alone land roughly around fifteen to twenty-five million euros, or about sixteen to twenty-seven million US dollars — and Wikipedia notes the job rivaled Florence’s annual defense budget. The Gates of Paradise, commissioned in 1425 and finished in 1452, cost nearly as much again.",
        "Those eastern doors — Michelangelo nicknamed them the Gates of Paradise — are now museum originals with replicas on the building. Ten gilded panels tell Old Testament stories in perspective that still startles. Rebuild the entire baptistery today with imported marble cladding and three full bronze door campaigns, and a cautious modern estimate sits around one hundred to two hundred million euros — roughly one hundred ten to two hundred twenty million US dollars — before you price the irreplaceable artistry.",
        "Stand here a moment: guild wealth, baptismal politics, and bronze that cost as much as an army. Then leave the square south along Via dei Calzaiuoli toward the civic center."
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
      audio: "audio/03-repubblica.mp3",
      durationSec: 47,
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
      audio: "audio/04-orsanmichele.mp3",
      durationSec: 45,
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
      audio: "audio/05-signoria.mp3",
      durationSec: 53,
      photos: [
        {
          src: "images/signoria/david-replica.jpg",
          caption: "Michelangelo’s David (replica) at Palazzo Vecchio"
        },
        {
          src: "images/signoria/hercules-cacus.jpg",
          caption: "Hercules and Cacus — Baccio Bandinelli"
        },
        {
          src: "images/signoria/neptune-fountain.jpg",
          caption: "Fountain of Neptune — Bartolomeo Ammannati"
        },
        {
          src: "images/signoria/judith-holofernes.jpg",
          caption: "Judith and Holofernes — Donatello"
        },
        {
          src: "images/signoria/palace-door.jpg",
          caption: "Guarded doorway — Palazzo Vecchio"
        }
      ],
      script: [
        "Piazza della Signoria is Florence without soft edges. Palazzo Vecchio’s fortress tower still watches the square where the Republic debated, Medici ruled, and Savonarola burned.",
        "Face the palace. A copy of Michelangelo’s David stands where the original once guarded the doorway — a republican emblem of defiant youth. Beside him, Bandinelli’s Hercules and Cacus flexes Medici muscle; Ammannati’s Neptune rises from the fountain; Donatello’s Judith still raises her sword.",
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
      audio: "audio/06-ponte-vecchio.mp3",
      durationSec: 75,
      photos: [
        {
          src: "images/signoria/david-replica.jpg",
          caption: "You leave David at the palace door — the Republic’s nerve, staring toward the river."
        },
        {
          src: "images/signoria/hercules-cacus.jpg",
          caption: "Hercules and Cacus: Medici muscle beside the doorway the Vasari Corridor escapes."
        },
        {
          src: "images/signoria/neptune-fountain.jpg",
          caption: "Neptune’s fountain — the square’s sea god before you trade stone for the Arno."
        },
        {
          src: "images/signoria/judith-holofernes.jpg",
          caption: "Judith’s raised sword: civic warning you carry in mind as you walk to the bridge."
        },
        {
          src: "images/signoria/palace-door.jpg",
          caption: "Palazzo Vecchio’s guarded door — start of the private skyway over Ponte Vecchio."
        }
      ],
      script: [
        "You have just left Florence’s outdoor sculpture court. David still guards the palace door; Hercules pins Cacus in Medici triumph; Neptune claims the fountain; Judith lifts her blade. That whole allegory of power sits behind you now — and the Medici preferred not to walk through it with everyone else.",
        "From those palace walls, Giorgio Vasari built a corridor that slips above the street, through the Uffizi, and out across the Ponte Vecchio — a private skyway so rulers could move from Palazzo Vecchio to Palazzo Pitti without touching the crowd. Look up at the eastern shops: that enclosed passage is their escape hatch from the square of statues.",
        "The bridge itself has stood since 1345. Butchers clung here first; Cosimo de’ Medici swapped them for goldsmiths so the corridor above would smell of metal, not meat. Stand mid-span: the Arno stretches both ways, ochre walls and green shutters, the only historic bridge to survive 1944.",
        "Cross fully into the Oltrarno. You have walked from marble myth to working gold — Florence’s argument between republic, dynasty, and river. Your next stop is just beyond, on the quieter south bank."
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
      audio: "audio/07-oltrarno.mp3",
      durationSec: 50,
      script: [
        "You are now in the Oltrarno — literally ‘beyond the Arno.’ This bank feels more lived-in: workshops, neighborhood trattorie, laundry lines, the hum of a Florence that is not only a museum.",
        "Ahead, Palazzo Pitti spreads like a stone cliff. The Medici bought it and made it their grand residence; the Boboli Gardens climb the hill behind. Even if you skip the ticket lines today, notice how the palace turns its back on the river and claims the slope.",
        "Artisans still work leather and wood a few streets west toward Santo Spirito. If you have time after the tour, wander there for a slower Florence.",
        "For the next stop, head east along the south bank — Via de’ Bardi / Via di San Niccolò — then climb toward Piazzale Michelangelo. The hill is real; take your time."
      ]
    },
    {
      id: "piazzale-michelangelo",
      order: 8,
      name: "Piazzale Michelangelo",
      shortName: "Piazzale",
      lat: 43.7629,
      lng: 11.265,
      walkFromPrev: "From the Oltrarno, walk east (Via de’ Bardi / San Niccolò), then up to the terrace — about 15–20 minutes uphill.",
      audio: "audio/09-piazzale-michelangelo.mp3",
      durationSec: 50,
      script: [
        "You have earned this view. Piazzale Michelangelo is Florence’s balcony — laid out in the 1860s when the city briefly served as Italy’s capital and wanted a stage for its own skyline.",
        "The bronze David here is a replica; the original lives at the Accademia. Still, he faces the city he once guarded in stone, and the panorama does the rest: Duomo, Palazzo Vecchio, bridges stitched across the Arno, hills fading to blue.",
        "Sunset crowds gather for a reason. Even at midday, trace the route you have already walked — from the marble cathedral down through the civic squares and over the goldsmiths’ bridge.",
        "When you leave, descend toward Porta San Niccolò and cross the river again (Ponte alle Grazie or nearby), then walk to Piazza Santa Croce for the final stop."
      ]
    },
    {
      id: "santa-croce",
      order: 9,
      name: "Piazza Santa Croce",
      shortName: "Santa Croce",
      lat: 43.7687,
      lng: 11.262,
      walkFromPrev: "Descend from the piazzale, cross the Arno (Ponte alle Grazie), then continue to Piazza Santa Croce.",
      audio: "audio/09-santa-croce.mp3",
      durationSec: 56,
      script: [
        "Piazza Santa Croce opens wide before the Franciscan basilica — Florence’s pantheon. Inside rest Michelangelo, Galileo, Machiavelli, Rossini; outside, the façade’s Star of David recalls architect Matas and the square’s long civic life.",
        "This piazza has hosted tournaments, sermons, and the Calcio Storico — a violent Renaissance football still played in June on sand dumped over these stones.",
        "Stand with your back to the church and look toward the hills. You have walked faith, guild, republic, river, viewpoint, and memory. The dome you started beneath still punctures the skyline if you know where to glance.",
        "Your tour ends here. Rest on the steps, find a gelato, or step inside Santa Croce when the light is soft. Grazie for walking with Passi — Florence rewards those who move at the city’s own pace."
      ]
    }
  ]
};
