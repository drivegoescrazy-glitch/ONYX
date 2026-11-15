#!/usr/bin/env python3
"""Build the 500,000-record conversation pack.

The pack is generated from conversational scenarios. Each scenario has line
templates (what a person says), replies in several registers, and guidance
questions ("how do I respond when..."). Slots — names, times, days, topics,
places, products — are filled combinatorially, so the pack covers many
phrasings of the same social situation without repeating a line.

Output: training/conversation/part-NN.jsonl, 100,000 records per part.
"""

import argparse
import itertools
import json
import re
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "training" / "conversation"
TOTAL = 500000
PART_SIZE = 100000

NAMES = [
    "Sam", "Priya", "Alex", "Maria", "Tom", "Aisha", "Ben", "Chen", "Dana", "Eli",
    "Fatima", "Grace", "Hugo", "Ivy", "Jamal", "Kai", "Lena", "Marco", "Nina", "Omar",
    "Pablo", "Quinn", "Rosa", "Sami", "Tara", "Umberto", "Vera", "Wei", "Xena", "Yusuf",
    "Zoe", "Ana", "Bo", "Cara", "Dev", "Eve", "Finn", "Gina", "Hal", "Ines",
    "Jonas", "Kira", "Liam", "Maya", "Noah", "Olga", "Piet", "Ravi", "Sofia", "Theo",
    "Uma", "Viktor", "Willa", "Yara", "Zane", "Amara", "Bilal", "Cleo", "Dario", "Esme",
    "Farid", "Greta", "Hana", "Idris", "Juno", "Karim", "Leila", "Milo", "Nadia", "Owen",
    "Petra", "Rafael", "Selin", "Tomas", "Ursula", "Vince", "Wendy", "Yann", "Zara", "Arun",
    "Bea", "Cyrus", "Delia", "Emeka", "Fiona", "Gus", "Hiro", "Iris", "Jules", "Kofi",
    "Lucia", "Mateo", "Noor", "Otto", "Pia", "Rhea", "Sven", "Tessa", "Umar", "Vera",
    "Wes", "Yuki", "Zoha", "Adil", "Bree", "Cato", "Dima", "Elsa", "Fred", "Gita",
    "Hector", "Imran", "Jada", "Kemal", "Lars", "Mira", "Nils", "Orla", "Pavel", "Rina",
]
TIMES = [
    "7am", "8am", "9am", "9:30", "10am", "10:30", "11am", "11:45", "noon", "12:30",
    "1pm", "1:30", "2pm", "2:30", "3pm", "3:30", "4pm", "4:15", "4:45", "5pm",
    "5:30", "6pm", "6:30", "7pm", "8pm", "9am tomorrow", "2pm tomorrow",
]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
TOPICS = [
    "deadline", "budget", "new hire", "client call", "outage",
    "roadmap", "invoice", "design review", "test failures", "release",
    "holiday plan", "football match", "weather", "traffic", "new café",
    "office move", "training session", "interview panel", "audit", "quarterly report",
    "onboarding doc", "pricing page", "support queue", "security review", "backlog",
    "sprint plan", "hiring plan", "content calendar", "vendor contract", "renewal",
    "office refit", "travel booking", "team offsite", "lunch order", "shift rota",
    "conference talk", "blog post", "demo script", "data migration", "api change",
    "access request", "incident report", "monthly numbers", "customer complaint", "board deck",
    "sales pipeline", "on-call handover", "budget forecast", "contract review", "product launch",
    "website refresh", "email campaign", "training budget", "new laptop order", "office plants",
    "car booking", "meeting notes", "action list", "risk register", "holiday cover",
]

PLACES = [
    "station", "café on the corner", "third floor", "main entrance",
    "car park", "meeting room", "airport", "hotel lobby", "library",
    "co-working space", "supermarket", "gym", "reception", "roof terrace",
    "conference room", "print room", "break room", "loading bay", "bus stop",
    "client office", "warehouse", "lab", "studio", "lecture hall", "canteen",
    "bike shed", "side entrance", "back stairs", "front desk", "meeting pod",
    "coffee stand", "quiet room", "training room", "basement", "annex",
    "north wing", "south gate", "visitor centre", "service desk", "staff room",
]
PRODUCTS = [
    "laptop", "monitor", "invoice", "report", "ticket", "order",
    "subscription", "headset", "printer", "licence", "badge", "keyboard",
    "phone", "tablet", "dock", "charger", "cable", "webcam", "microphone",
    "speaker", "router", "server rack", "backup drive", "software key",
    "support contract", "warranty", "delivery", "courier parcel", "quote",
    "purchase order", "credit note", "statement", "receipt", "booking",
    "access pass", "parking permit", "training seat", "seat licence",
    "conference pass", "health check",
]

DISHES = [
    "chicken sandwich", "mushroom risotto", "beef burger", "veggie wrap", "fish and chips",
    "caesar salad", "margherita pizza", "lentil soup", "pad thai", "steak",
    "omelette", "club sandwich", "ramen", "falafel plate", "pasta bake",
    "pancakes", "sushi set", "kebab", "quiche", "jacket potato",
]

SLOTS = {
    "name": NAMES,
    "time": TIMES,
    "day": DAYS,
    "topic": TOPICS,
    "place": PLACES,
    "product": PRODUCTS,
    "dish": DISHES,
}

# Each scenario:
#   tags      what the record is about
#   lines     what the person says, with {slots}
#   replies   a natural answer, in a few registers
#   asks      guidance questions about how to handle the situation
#   advice    the guidance answer, with {slots}
SCENARIOS = [
    {
        "tags": ["chat", "greeting"],
        "lines": [
            "hi {name}", "hey {name}, how's it going", "morning {name}", "hello {name}",
            "hi {name}, quick question", "hey, you around {name}", "{name}, good to see you",
            "afternoon {name}, how are you", "hi {name}, got a minute", "hey {name}, you there",
        ],
        "replies": [
            "Hey {name} — good to hear from you. What's up?",
            "Hi! I'm around. What do you need?",
            "Hey, good to see you. How's your day going?",
            "Morning! What can I do for you?",
        ],
        "asks": [
            "how do i greet a colleague in the morning",
            "how do i say hi without sounding formal",
            "what is a good way to open a work chat",
            "how do i greet someone i have not spoken to in a while",
        ],
        "advice": "Keep it short and give them something to answer: \"Morning, {name} — how's the {topic} going?\" A greeting plus one question works better than a bare hello, and it costs nothing to add their name.",
    },
    {
        "tags": ["chat", "how-are-you"],
        "lines": [
            "how are you", "how's it going {name}", "how have you been", "{name}, how are you doing",
            "you good?", "how's your week going", "everything alright {name}", "how are things",
        ],
        "replies": [
            "Pretty good, thanks — busy week. How about you?",
            "Not bad at all. How's yours going?",
            "Good, thanks. Bit of a long day, but fine. You?",
            "All good here. What about you, {name}?",
        ],
        "asks": [
            "how do i answer how are you without oversharing",
            "what do i say when someone asks how i am",
            "how do i answer how are you honestly",
        ],
        "advice": "\"How are you\" is usually a greeting, not a question about your health. Answer in four or five words and hand it back: \"Good, thanks — you?\" If you actually want to talk about the {topic}, say so in a second sentence: \"Actually, I've been chasing the {topic} all morning.\"",
    },
    {
        "tags": ["chat", "introduction"],
        "lines": [
            "hi, i'm {name}", "i don't think we've met — i'm {name}", "{name}, by the way",
            "i'm new here, {name}", "i just joined the team, i'm {name}",
            "we met at the {place} — i'm {name}", "sorry, your name again? i'm {name}",
        ],
        "replies": [
            "Nice to meet you, {name}. I'm on the team that handles the {topic}.",
            "Good to meet you, {name}! How are you finding it so far?",
            "Hi {name} — welcome. If you need anything for the {topic}, just ask.",
        ],
        "asks": [
            "how do i introduce myself in a new team",
            "how do i introduce myself without sounding nervous",
            "what should i say when i meet a new colleague",
        ],
        "advice": "Two sentences is plenty: your name, then one detail they can pick up. \"Hi, I'm {name} — I've just joined and I'm looking after the {topic}.\" Then ask them something. Nerves usually show as talking too long, not as saying too little.",
    },
    {
        "tags": ["chat", "thanks"],
        "lines": [
            "thanks {name}", "thank you so much", "thanks a lot for the {product}",
            "cheers {name}", "appreciate it", "thanks for sorting the {topic}",
            "that was really helpful, thank you",
        ],
        "replies": [
            "You're welcome — glad it helped.",
            "No problem at all, {name}.",
            "Anytime. Let me know if the {topic} needs anything else.",
            "Happy to help. Shout if it comes up again.",
        ],
        "asks": [
            "how do i respond when someone thanks me",
            "how do i reply to thanks in a work chat",
            "is no problem rude in english",
        ],
        "advice": "\"You're welcome\", \"No problem\" and \"Happy to help\" all work; pick one and add a small forward-looking line for a work context: \"Anytime — tell me if the {topic} shifts.\" Avoid the flat \"no problem\" with someone senior if the favour was large; it can sound dismissive.",
    },
    {
        "tags": ["chat", "apology"],
        "lines": [
            "sorry i'm late", "sorry, i missed your message", "apologies for the delay on the {topic}",
            "sorry about the {product}", "i'm sorry, that was my mistake",
            "sorry for the confusion earlier", "sorry i forgot to reply",
        ],
        "replies": [
            "No worries — these things happen.",
            "It's fine, thanks for telling me. What's the plan for the {topic}?",
            "Don't worry about it. Can we get the {product} sorted today?",
        ],
        "asks": [
            "how do i apologise for being late",
            "how do i apologise in a work email",
            "how do i say sorry without over apologising",
        ],
        "advice": "Name the thing and the fix in one breath: \"Sorry I'm late — the {place} was chaos. I'll pick up the {topic} now.\" One apology is enough; repeating it moves the conversation from the problem to your discomfort.",
    },
    {
        "tags": ["chat", "help"],
        "lines": [
            "can you help me with the {topic}", "could you take a look at the {product}",
            "i'm stuck on the {topic}, got five minutes", "{name}, any idea how to fix the {product}",
            "could you show me how you did the {topic}", "i need a hand with the {product} today",
        ],
        "replies": [
            "Sure — send me what you have and I'll take a look.",
            "Yes, I've got ten minutes now. What's failing?",
            "Happy to. Is it blocking the {topic}?",
        ],
        "asks": [
            "how do i ask for help at work without sounding incompetent",
            "how do i ask a colleague for five minutes",
            "how do i ask for help over chat",
        ],
        "advice": "Say what you tried, then ask for the smallest thing you need: \"I've checked the {product} twice and I'm stuck on the {topic} — could you look for five minutes?\" That gives them a starting point and makes saying yes cheap.",
    },
    {
        "tags": ["chat", "clarification"],
        "lines": [
            "sorry, i didn't catch that", "can you say that again", "which {place} do you mean",
            "do you mean the {product} or the {topic}", "sorry, what was the last part",
            "could you spell that", "i'm not sure i follow — the {topic}?",
        ],
        "replies": [
            "Sorry — I meant the {topic}, not the {product}.",
            "Let me try again: we meet at the {place} at {time}.",
            "Of course. The short version: {name} owns the {topic} until {day}.",
        ],
        "asks": [
            "how do i ask someone to repeat themselves politely",
            "how do i say i didn't understand without sounding rude",
            "how do i ask for clarification in a meeting",
        ],
        "advice": "Name the part you did understand — it saves the other person repeating everything: \"I've got the {topic} part — was the deadline {day} or {time}?\" For a word you missed, ask about the word itself.",
    },
    {
        "tags": ["chat", "interrupting"],
        "lines": [
            "sorry to jump in", "can i stop you there", "quick thing before i forget",
            "may i add something", "sorry — one correction on the {topic}",
        ],
        "replies": [
            "Go ahead — what's the correction?",
            "Of course, what did I miss?",
            "Sure, one second — then I'll finish the {topic}.",
        ],
        "asks": [
            "how do i interrupt someone politely in a meeting",
            "how do i cut in without being rude",
            "how do i correct someone mid sentence",
        ],
        "advice": "Signal, say the thing, hand it back: \"Sorry to jump in — the {product} number is wrong. Carry on.\" Keep it to one sentence; repeated interruptions read as rude even when each one is polite.",
    },
    {
        "tags": ["chat", "small-talk"],
        "lines": [
            "cold today, isn't it", "did you see the {topic} news", "any plans for {day}",
            "how was your weekend", "busy day?", "did you get caught in the rain at the {place}",
            "are you coming to the {place} later",
        ],
        "replies": [
            "Freezing. I'm not leaving the building until {time}.",
            "Quiet one, thankfully. You?",
            "Nothing fixed — maybe the {place} if the weather holds.",
        ],
        "asks": [
            "what are good small talk topics at work",
            "how do i make small talk without it being awkward",
            "what should i avoid in small talk",
        ],
        "advice": "Comment plus question: \"Cold one — did you get caught at the {place}?\" Then follow up on whatever they say. Two or three exchanges is plenty; steer clear of money, health, politics and anyone's relationship status.",
    },
    {
        "tags": ["chat", "plans"],
        "lines": [
            "fancy a coffee at {time}", "are you free on {day}", "shall we meet at the {place}",
            "can we move our catch-up to {time} on {day}", "lunch on {day}?",
            "want to grab a coffee before the {topic} meeting",
        ],
        "replies": [
            "Yes — {time} at the {place} works for me.",
            "I can do {day} at {time}. Shall I book the {place}?",
            "Can't do {day}, but {time} the next day is free.",
        ],
        "asks": [
            "how do i suggest a meeting time",
            "how do i make plans without being pushy",
            "how do i confirm a plan so we don't mix it up",
        ],
        "advice": "Offer a specific time and place, then repeat it back once agreed: \"Great — {day} at {time}, at the {place}.\" Vague plans (\"sometime next week\") are the ones that quietly die.",
    },
    {
        "tags": ["chat", "declining"],
        "lines": [
            "can you take the {topic} today", "are you coming to the {place} on {day}",
            "could you join the {topic} call at {time}", "would you review the {product} tonight",
        ],
        "replies": [
            "I can't take it today, but I can do {day} morning.",
            "Not this time, sorry — I'm on the {topic} until {time}. Ask me again next week?",
            "I'd rather not commit unless it's urgent — is {day} soon enough?",
        ],
        "asks": [
            "how do i say no to extra work politely",
            "how do i decline a meeting invite without offending anyone",
            "how do i say no and still be helpful",
        ],
        "advice": "Decline clearly and offer what you can: \"I can't do the {topic} today. I could pick it up {day} — does that still work?\" A vague \"maybe later\" makes people ask again, which is worse than a clean no.",
    },
    {
        "tags": ["chat", "phone"],
        "lines": [
            "hello, it's {name} from the {place}", "is now a good time to talk",
            "i'm calling about the {product}", "can you hear me",
            "sorry, you're breaking up", "let me read that back to you",
            "could you spell your surname for me",
        ],
        "replies": [
            "Yes, now works. What's happened with the {product}?",
            "I can hear you — go ahead.",
            "Could you repeat the reference? The line dropped for a second.",
        ],
        "asks": [
            "how do i start a phone call in english",
            "how do i ask someone to repeat themselves on the phone",
            "how do i end a phone call politely",
        ],
        "advice": "Open with who you are and why you're calling: \"Hi, this is {name} — I'm calling about the {product}.\" Then read back names, numbers and dates. Phone audio strips the redundancy that makes speech easy to follow.",
    },
    {
        "tags": ["chat", "directions"],
        "lines": [
            "excuse me, how do i get to the {place}", "is the {place} far from here",
            "which way to the {place}", "do i turn left at the {place}",
            "how long does it take to walk to the {place}",
        ],
        "replies": [
            "Go straight on, then turn right at the {place} — about five minutes.",
            "It's behind the {place}; two minutes on foot.",
            "Take the second left after the {place}. You'll see it opposite the {topic} sign.",
        ],
        "asks": [
            "how do i ask for directions in english",
            "how do i repeat directions back to check them",
            "what are common direction phrases in english",
        ],
        "advice": "Ask, then echo it back: \"So, left at the {place}, then straight on?\" Useful phrases: go straight on, turn left, at the lights, opposite, next to, across from. \"I'm trying to find the {place}\" gets better help than \"where is\".",
    },
    {
        "tags": ["chat", "shopping"],
        "lines": [
            "how much is the {product}", "do you have this in a medium",
            "can i try this on", "is the {product} in stock",
            "do you take contactless", "could i have a receipt for the {product}",
        ],
        "replies": [
            "That one's {product} — I'll check the size for you.",
            "Yes, we have it in stock. Would you like me to hold it?",
            "Card and contactless both work. I'll print the receipt.",
        ],
        "asks": [
            "how do i ask about a price in a shop",
            "how do i ask to try something on",
            "how do i say i'm just looking politely",
        ],
        "advice": "\"Excuse me — how much is the {product}?\" is enough. If you're not buying, \"I'm just browsing, thanks\" closes the sales pitch without offence.",
    },
    {
        "tags": ["chat", "food"],
        "lines": [
            "could i get the {dish}, please", "table for two at {time}",
            "is the {dish} vegetarian", "could we get the bill",
            "what do you recommend", "can i change my order to the {dish}",
        ],
        "replies": [
            "Of course — the {dish} for two, at {time}?",
            "Yes, the {dish} is vegetarian. Anything to drink with that?",
            "I'll bring the bill over. Card or cash?",
        ],
        "asks": [
            "how do i order food in english",
            "how do i ask for the bill in a restaurant",
            "how do i ask about allergies when ordering",
        ],
        "advice": "\"Could I get the {product}, please?\" then answer the follow-ups (for here or to go, anything else). Say restrictions up front — \"I'm allergic to nuts, does this contain any?\" — and close with \"Could we get the bill, please?\"",
    },
    {
        "tags": ["chat", "support"],
        "lines": [
            "the {product} still isn't working", "i've been waiting since {time} for the {topic}",
            "this is the third time i've called about the {product}",
            "can you escalate the {topic}", "i want a refund for the {product}",
            "nobody has replied to my email about the {topic}",
        ],
        "replies": [
            "I'm sorry — let me pull up the {topic} and see where it stopped.",
            "That's not the experience we want. I'll escalate the {product} now and confirm by {time}.",
            "I can start the refund for the {product} today. Can I confirm the order reference?",
        ],
        "asks": [
            "how do i complain politely but firmly",
            "how do i handle an angry customer",
            "how do i ask for an escalation without threatening",
        ],
        "advice": "Acknowledge, then commit to an action and a time: \"I'm sorry the {product} failed again. I'll escalate it now and come back to you by {time}.\" Repeat the commitment in writing; that is what de-escalates a third call.",
    },
    {
        "tags": ["chat", "workplace"],
        "lines": [
            "i don't think that plan works for the {topic}", "can i push back on the {topic}",
            "i'd worry about the timeline for the {product}", "i see it differently",
            "that's not what the {topic} needs", "i'm not convinced by the {product} approach",
        ],
        "replies": [
            "Fair — what would you change about the {topic}?",
            "That's a reasonable worry. What would make the {product} safer?",
            "I hear you. Let's compare both options before {day}.",
        ],
        "asks": [
            "how do i disagree with my manager politely",
            "how do i push back on a plan in a meeting",
            "how do i criticise an idea without attacking the person",
        ],
        "advice": "Acknowledge, then disagree with the idea, not the person: \"I see the appeal, though I'd worry the {topic} slips past {day}.\" Ask a question instead of making a verdict — it moves the room from defending to solving.",
    },
    {
        "tags": ["chat", "feedback"],
        "lines": [
            "can i give you some feedback on the {topic}", "that {product} needs work",
            "the {topic} missed what we agreed", "what did you think of my {topic}",
            "any notes on the {product} before {day}", "be honest — how was it",
        ],
        "replies": [
            "Yes, please — specific is more useful than kind.",
            "The structure of the {topic} worked; the numbers need a source before {day}.",
            "One thing: the {product} buries the ask. Lead with it.",
        ],
        "asks": [
            "how do i give negative feedback kindly",
            "how do i ask for feedback without sounding needy",
            "how do i receive criticism well",
        ],
        "advice": "Give one specific observation, one effect, one change: \"The {topic} opens with background, so the ask lands late — moving it up top would help.\" When receiving, ask a question rather than defending: \"Which part read as unclear?\"",
    },
    {
        "tags": ["chat", "supportive"],
        "lines": [
            "i'm completely swamped with the {topic}", "i'm having a rough week",
            "the {product} keeps breaking and i'm done", "i don't think i can finish by {day}",
            "i'm nervous about the {topic} tomorrow", "i messed up the {topic}",
        ],
        "replies": [
            "That sounds exhausting. What would take the most pressure off today?",
            "That's a lot at once. Do you want help with the {product}, or just to vent?",
            "For what it's worth, the {topic} is recoverable. What's the first step?",
        ],
        "asks": [
            "how do i support a stressed colleague",
            "what do i say when someone is overwhelmed",
            "how do i comfort someone without giving advice",
        ],
        "advice": "Name it, then ask what they want: \"That's a rough week. Do you want help with the {topic}, or just to talk?\" Offering advice before they ask reads as dismissing the feeling.",
    },
    {
        "tags": ["chat", "congratulations"],
        "lines": [
            "i got the {topic} role", "we shipped the {product} on {day}",
            "i passed the interview", "the {topic} went through",
            "my project got funded", "i'm starting at the {place} on {day}",
        ],
        "replies": [
            "That's brilliant news — congratulations!",
            "Well done! The {topic} was a long haul.",
            "Great result, {name}. Enjoy it before the next thing lands.",
        ],
        "asks": [
            "how do i congratulate someone at work",
            "how do i say well done without sounding generic",
            "what do i say when someone gets promoted",
        ],
        "advice": "Be specific about what they did: \"Congratulations — the {topic} took real persistence.\" Then one question, not a speech: \"What's first on the list?\"",
    },
    {
        "tags": ["chat", "sympathy"],
        "lines": [
            "my {topic} didn't work out", "i didn't get the role", "we lost the {topic} account",
            "my dog died yesterday", "i'm dealing with a family thing",
        ],
        "replies": [
            "I'm sorry — that's hard. I'm here if you want to talk, and I'll cover the {topic} today.",
            "That's a real loss. Take the time you need; the {product} can wait.",
            "I'm sorry to hear it. Let me know what would help, even if it's nothing.",
        ],
        "asks": [
            "what do i say when someone's relative dies",
            "how do i respond when a colleague gets bad news",
            "how do i offer help without being intrusive",
        ],
        "advice": "Short and plain beats clever: \"I'm so sorry. I'm here if you want to talk.\" Offer something concrete — covering the {topic}, moving the {product} — and accept \"no\" without pushing.",
    },
    {
        "tags": ["chat", "goodbye"],
        "lines": [
            "anyway, i should get back to it", "let's catch up soon {name}",
            "i'll let you go", "speak on {day}", "thanks, i'll send the {product} over",
            "right, back to the {topic}",
        ],
        "replies": [
            "Sounds good — talk on {day}.",
            "Thanks for the update. Send the {product} when you can.",
            "Good talking to you. I'll pick up the {topic} tomorrow.",
        ],
        "asks": [
            "how do i end a conversation politely",
            "how do i leave a chat without being rude",
            "how do i close an email politely",
        ],
        "advice": "Signal, thank, close: \"Anyway, I should get back to the {topic} — good talking to you.\" If you promised something, name it as you leave: \"I'll send the {product} today.\"",
    },
    {
        "tags": ["chat", "interview"],
        "lines": [
            "tell me about yourself", "why do you want this role",
            "what's your biggest weakness", "where do you see yourself in five years",
            "why are you leaving your current job", "do you have any questions for us",
        ],
        "replies": [
            "I've spent four years on the {topic}, mostly making {product} work reliable — I'd like to do that at a larger scale.",
            "A weakness I've worked on: I used to over-prepare the {topic}. Now I timebox the first draft and review it with someone.",
            "One question: what does success look like for this role in the first six months?",
        ],
        "asks": [
            "how do i answer tell me about yourself",
            "how do i answer what is your weakness",
            "what questions should i ask in an interview",
        ],
        "advice": "Use situation, action, result, and keep it under 90 seconds: \"The {topic} took a day; I automated the export; now it takes ten minutes.\" For weaknesses, name something real and the change you made.",
    },
    {
        "tags": ["chat", "handover"],
        "lines": [
            "i'm off on {day} — here's where the {topic} stands",
            "can you cover the {product} while i'm away",
            "who's picking up the {topic} next week",
            "i'll be out until {time} tomorrow",
        ],
        "replies": [
            "Noted. Send me the {topic} notes and I'll keep it moving until {day}.",
            "I can cover the {product}. Anything that can't wait?",
            "Thanks — who do I ask if the {product} breaks?",
        ],
        "asks": [
            "how do i hand over work before leave",
            "how do i write a handover note",
            "how do i ask a colleague to cover for me",
        ],
        "advice": "Three lines: what is in flight, what is urgent, who to ask. \"{topic} is with the client until {day}; the {product} renews {time} — ping {name} if it breaks.\" Then confirm they have access.",
    },
    {
        "tags": ["chat", "standup"],
        "lines": [
            "what did you do yesterday", "any blockers on the {topic}",
            "where are we on the {product}", "what's the plan for today",
            "is the {topic} still on track for {day}",
        ],
        "replies": [
            "Yesterday: finished the {topic} review. Today: the {product} fix. No blockers.",
            "On track for {day}, but I need a decision on the {product} by {time}.",
            "One blocker: waiting on the {place} team for access.",
        ],
        "asks": [
            "how do i give a standup update",
            "how do i say i'm blocked without blaming anyone",
            "how do i report progress on a project",
        ],
        "advice": "Done, doing, blocked — in that order, one line each. \"Finished the {topic}; today the {product}; blocked on access from the {place} team.\" Naming the blocker with a needed-by time is what gets it cleared.",
    },
    {
        "tags": ["chat", "negotiation"],
        "lines": [
            "can we move the deadline to {day}", "is there flexibility on the price",
            "i'd like to discuss my salary", "can we reduce the scope of the {topic}",
            "what would it take to deliver by {day}",
        ],
        "replies": [
            "We could hit {day} if we drop the {product} from this round.",
            "There's some room on price if the volume holds.",
            "I can move on salary if the {topic} ownership comes with it.",
        ],
        "asks": [
            "how do i ask for a deadline extension",
            "how do i negotiate a salary politely",
            "how do i negotiate price without damaging the relationship",
        ],
        "advice": "Trade, don't plead: \"{day} is possible if we drop the {product} this round — otherwise I need until {time} the following week.\" Say what you want first, then the constraint; ending on your number keeps the anchor.",
    },
]


# Natural continuations added to a line, keyed by the scenario's second tag.
# They bring in topic, time and place, which is what turns a few hundred
# phrasings into a large, still-readable set.
SUFFIXES = {
    "greeting": [" — is the {topic} still on for {time}?", ", can we talk about the {topic} at {time}?", " — see you at the {place} at {time}."],
    "how-are-you": [" — still chasing the {topic}?", ", how's the {topic} treating you?", " — are you at the {place} today?"],
    "introduction": [", i'm covering the {topic} from {day}", " — i'll be at the {place} on {day}", ", i've taken over the {topic} from {time}"],
    "thanks": [" for the {topic} earlier", " — the {product} works now", " for your help at the {place}"],
    "apology": [" — the {place} was a mess at {time}", ", i'll get the {topic} to you by {time}", " — i'll redo the {product} today"],
    "help": [" — the {product} won't load", ", i'm stuck on the {topic} until {time}", " before the {topic} review on {day}"],
    "clarification": [" — was that {time} or {day}?", ", the {topic} or the {product}?", " — which {place} did you mean?"],
    "interrupting": [" — the {topic} number looks off", ", the {product} shipped without the fix", " — we're past {time} on the {topic}"],
    "small-talk": [" — did you get to the {place}?", ", any plans for {day}?", " — how's the {topic} going?"],
    "plans": [" at the {place} on {day}", " about the {topic} at {time}", " before the {topic} call on {day}"],
    "declining": [" — i'm on the {topic} until {time}", ", can it wait until {day}?", " — the {product} is due at {time}"],
    "phone": [" about the {product} — is {time} still ok?", ", the {topic} is down since {time}", " — i'm at the {place} until {day}"],
    "directions": [" from the {place}", " before {time}", " — i'm near the {topic} office"],
    "shopping": [" — the {product} in the window", " by {time} today", " at the {place} branch"],
    "food": [" at {time} on {day}", " — and a table near the {place}", " with the {topic} menu"],
    "support": [" — the {product} is still down", " since {time} on {day}", ", the {topic} has failed twice"],
    "workplace": [" — the {topic} slips past {day}", ", the {product} needs another week", " after the {place} meeting at {time}"],
    "feedback": [" — the {topic} felt rushed", ", the {product} needs one more pass", " before {day}"],
    "supportive": [" — the {topic} is not moving", ", i'm behind on the {product} for {day}", " since {time} this morning"],
    "congratulations": [" — the {topic} finally landed", ", we shipped the {product} on {day}", " — starting at the {place} on {day}"],
    "sympathy": [" — the {topic} fell through", ", and the {product} was due {day}", " — i'll be off until {time}"],
    "goodbye": [" — i'll send the {product} by {time}", ", let's talk about the {topic} on {day}", " — back at the {place} tomorrow"],
    "interview": [" for the {topic} role", " — i ran the {product} programme at the {place}", " since {time} last year"],
    "handover": [" — the {topic} is with the client until {day}", ", the {product} renews at {time}", " from the {place} team"],
    "standup": [" on the {topic} since {time}", " — the {product} needs a decision by {day}", " before the {place} call"],
    "negotiation": [" — {day} is not realistic for the {topic}", ", the {product} scope has doubled since {time}", " given what we agreed at the {place}"],
}


def slots_in(template):
    return re.findall(r"\{(\w+)\}", template)


def fill(template, mapping, seed=0):
    """Fill a template, choosing deterministic values for slots it needs itself."""
    values = dict(mapping)
    for offset, key in enumerate(slots_in(template)):
        if key in values:
            continue
        pool = SLOTS[key]
        values[key] = pool[(seed + offset * 7) % len(pool)]
    text = template.format(**values)
    # templates sometimes say "the {place}" and the value can already read
    # naturally with an article; keep the prose clean either way.
    text = re.sub(r"\bthe the\b", "the", text, flags=re.I)
    text = re.sub(r"\bwhich the\b", "which", text, flags=re.I)
    text = re.sub(r"\bthe a\b", "the", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compatible_reply(scenario, mapping, seed):
    """Pick a reply that only mentions things the line already mentioned."""
    available = set(mapping)
    replies = scenario["replies"]
    fits = [reply for reply in replies if not (set(slots_in(reply)) - available)]
    pool = fits or replies
    return fill(pool[seed % len(pool)], mapping, seed)


def scenario_stream(scenario, counter):
    """Yield (question, answer, tags) for one scenario, cheapest first."""
    tags = scenario["tags"]
    lines = list(scenario["lines"])
    suffixes = SUFFIXES.get(tags[-1] if len(tags) > 1 else tags[0], [])
    for suffix in suffixes:
        lines.extend(line + suffix for line in scenario["lines"][:5])
    for line in lines:
        keys = slots_in(line)
        pools = [SLOTS[key] for key in keys]
        for combo in itertools.product(*pools) if keys else [()]:
            mapping = dict(zip(keys, combo))
            question = fill(line, mapping)
            reply = compatible_reply(scenario, mapping, counter[0])
            counter[0] += 1
            yield question, reply, tags
    for index, ask in enumerate(scenario["asks"]):
        keys = slots_in(ask)
        pools = [SLOTS[key] for key in keys]
        for combo in itertools.product(*pools) if keys else [()]:
            mapping = dict(zip(keys, combo))
            question = fill(ask, mapping)
            answer = fill(scenario["advice"], mapping, counter[0])
            counter[0] += 1
            yield question, answer, tags + ["how-to"]


def main():
    parser = argparse.ArgumentParser(description="Generate conversation training records")
    parser.add_argument("--total", type=int, default=TOTAL, help="how many records to write")
    parser.add_argument("--out", type=Path, default=None, help="write one single file instead of parts")
    parser.add_argument("--part-size", type=int, default=PART_SIZE)
    parser.add_argument("--lean", action="store_true", help="write only input and output, for the smallest file")
    args = parser.parse_args()

    total = args.total
    single = args.out
    if single:
        single.parent.mkdir(parents=True, exist_ok=True)
    else:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        for old in OUT_DIR.glob("part-*.jsonl"):
            old.unlink()

    seen = set()
    written = 0
    parts = 0
    handle = None
    counters = {index: [0] for index in range(len(SCENARIOS))}
    streams = [scenario_stream(scenario, counters[index]) for index, scenario in enumerate(SCENARIOS)]

    def open_target():
        nonlocal handle, parts
        if single:
            handle = single.open("w", encoding="utf-8")
            return
        if handle:
            handle.close()
            path = OUT_DIR / f"part-{parts:02d}.jsonl"
            print(f"{path.relative_to(ROOT)}: {args.part_size} records, {path.stat().st_size / 1024 / 1024:.1f} MB", flush=True)
        parts += 1
        handle = (OUT_DIR / f"part-{parts:02d}.jsonl").open("w", encoding="utf-8")

    open_target()
    # Round-robin so every scenario contributes evenly, until the pack is full.
    while written < total and streams:
        alive = []
        for stream in streams:
            try:
                question, answer, tags = next(stream)
            except StopIteration:
                continue
            alive.append(stream)
            key = hash(question.lower())
            if key in seen:
                continue
            seen.add(key)
            written += 1
            if args.lean:
                record = {"input": question, "output": answer}
            else:
                record = {"id": f"conv-{written:06d}", "input": question, "output": answer, "tags": tags}
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            if written % 500000 == 0:
                handle.flush()
                print(f"  {written:,} records", flush=True)
            if not single and written % args.part_size == 0 and written < total:
                open_target()
            if written >= total:
                break
        streams = alive

    if handle:
        handle.close()
    if single:
        size = single.stat().st_size
        print(f"{single}: {written:,} records, {size / 1024 / 1024:.1f} MB", flush=True)
    else:
        path = OUT_DIR / f"part-{parts:02d}.jsonl"
        print(f"{path.relative_to(ROOT)}: {written - (parts - 1) * args.part_size} records, {path.stat().st_size / 1024 / 1024:.1f} MB", flush=True)
    if written < total:
        raise SystemExit(f"only generated {written} unique lines; widen the slot banks")
    print(f"{written:,} records written")


if __name__ == "__main__":
    main()
