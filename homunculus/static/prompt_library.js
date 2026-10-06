// Preset animation prompts for UniMate, grouped by category. Each is ONE motion in the style UniMate was trained on
// (the server adds the leading "An object " and the full stop). Describe the motion, never the character.
export const LIBRARY = [
  { cat: "Walk & run", icon: "🚶", prompts: [
    "walks forward", "walks forward slowly", "walks forward briskly", "walks backward", "strolls casually with the arms swinging",
    "marches forward with the arms swinging high", "sneaks forward on tiptoe", "limps forward, favouring the left leg", "walks forward carrying something heavy",
    "jogs forward", "runs forward", "sprints forward as fast as possible", "runs forward and slows to a stop", "runs in a circle",
    "side-steps to the left", "side-steps to the right", "turns around on the spot", "walks forward and turns left", "walks forward and turns right" ] },
  { cat: "Jump & move", icon: "🦘", prompts: [
    "jumps in place", "jumps forward", "jumps up with both arms raised", "does a long leap forward", "hops on one leg", "skips forward happily",
    "crouches down low", "crouches and then jumps up", "rolls forward on the ground", "crawls forward on hands and knees", "climbs up a ladder",
    "steps up onto a high step", "falls forward and gets back up", "stumbles forward and catches its balance", "slides to a stop", "backflips" ] },
  { cat: "Idle & rest", icon: "🧍", prompts: [
    "stands still, breathing calmly", "stands idle and shifts its weight from foot to foot", "looks around slowly", "stretches the arms above the head",
    "stretches the back and rolls the shoulders", "yawns and stretches", "sits down on the ground", "stands up from sitting", "kneels down on one knee",
    "lies down on the back", "leans against a wall", "crosses the arms and waits impatiently", "taps a foot and looks at a watch", "shivers from the cold" ] },
  { cat: "Combat", icon: "⚔️", prompts: [
    "throws a punch with the right arm", "throws a quick left jab and a right cross", "throws an uppercut", "fights, throwing a punch and then a kick",
    "kicks forward with the right leg", "does a spinning kick", "does a roundhouse kick", "knees forward", "blocks with both arms raised",
    "dodges to the side", "ducks under an attack", "rolls away from an attack", "gets hit in the face and staggers back",
    "slashes forward with a sword", "swings a sword from overhead", "thrusts a sword forward", "draws a sword from the back", "raises a shield and blocks",
    "swings a heavy hammer down", "swings a staff in a circle", "charges forward and attacks", "falls to the knees defeated", "falls backward and lies still",
    "stands in a fighting stance, bouncing lightly", "cheers in victory with both fists raised" ] },
  { cat: "Ranged & magic", icon: "🏹", prompts: [
    "draws a bow and fires an arrow", "aims a rifle and shoots", "aims a pistol with both hands", "throws a ball overhand", "throws a spear forward",
    "casts a spell, raising both arms", "casts a fireball, thrusting the hand forward", "summons power, lifting both arms slowly", "channels energy, hands held out in front",
    "points forward and commands an attack", "reloads a weapon and looks around", "hides behind cover and peeks out" ] },
  { cat: "Dance", icon: "💃", prompts: [
    "dances hip hop, bouncing and swinging the arms", "dances salsa, stepping side to side and swaying the hips", "dances the tango, stepping slowly and sharply",
    "dances ballet, spinning on one foot", "dances disco, pointing an arm up and down", "dances the waltz, turning in circles", "breakdances, spinning on the ground",
    "dances like a robot, moving stiffly", "dances happily, jumping and clapping", "dances the cha-cha, stepping back and forth", "does a flamenco stomp with the arms raised",
    "moonwalks backward", "does a celebration dance with the arms waving", "sways side to side to slow music", "headbangs with the arms swinging", "twirls around with the arms out" ] },
  { cat: "Gestures & emotes", icon: "👋", prompts: [
    "waves with the right hand", "waves with both hands", "bows politely", "salutes", "claps the hands", "cheers with both arms raised",
    "shrugs the shoulders", "points forward", "beckons with one hand to come closer", "shakes its head no", "nods its head yes", "puts a hand on its chin, thinking",
    "scratches its head, confused", "covers its face with both hands", "facepalms", "laughs, bending forward and holding its stomach", "cries with the hands over the face",
    "stomps a foot angrily and shakes a fist", "puts both hands on the hips and looks proudly", "flexes both arms", "blows a kiss", "gives a thumbs up",
    "looks scared and backs away", "jumps in surprise and covers its mouth", "stops and holds up one hand", "greets with a small bow and an open hand" ] },
  { cat: "Sports & fitness", icon: "🏋️", prompts: [
    "kicks a ball", "swings a baseball bat", "swings a golf club", "serves a tennis ball", "shoots a basketball", "throws a football", "catches a ball with both hands",
    "does push-ups", "does squats", "does jumping jacks", "does sit-ups", "lifts a heavy barbell overhead", "stretches the legs before a race", "runs and does a long jump",
    "boxes, bobbing and throwing punches", "swims forward with an overarm stroke", "paddles a canoe", "skates forward gliding", "does yoga, balancing on one leg", "does a handstand" ] },
  { cat: "Everyday & work", icon: "🧰", prompts: [
    "drinks from a cup", "eats with one hand", "talks on a phone", "types on a keyboard", "reads a book", "opens a door and walks through", "knocks on a door",
    "picks up a box from the floor", "carries a heavy box forward", "puts a box down gently", "pushes a heavy object forward", "pulls a heavy rope", "hammers a nail",
    "chops wood with an axe", "sweeps the floor", "digs with a shovel", "waters plants", "washes the face", "brushes the teeth", "turns a wheel with both hands",
    "pulls a lever", "writes on a board", "sits at a desk and works", "plays a guitar", "plays a drum", "conducts an orchestra" ] },
  { cat: "Hero & drama", icon: "🦸", prompts: [
    "stands in a heroic pose with the hands on the hips", "poses proudly with the chest out", "lifts a fist toward the sky", "kneels and bows its head in respect",
    "takes a deep breath and prepares for battle", "looks up at the sky, astonished", "staggers forward, wounded", "drops to the knees and slumps", "pulls itself up from the ground, determined",
    "leaps off a ledge and lands in a crouch", "walks forward confidently, cape swaying", "turns slowly and looks over the shoulder", "strikes a dramatic pose with one arm extended",
    "sneaks up behind someone and strikes", "tiptoes carefully and freezes", "peeks around a corner" ] },
];
