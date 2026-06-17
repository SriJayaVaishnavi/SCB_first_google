"""Generate a realistic synthetic crisis-surge dataset for Beacon.

Grounded in the country feed: Hat Yai (Thailand) floods + Middle-East airspace
disruption. Produces ~300 messages with a realistic crisis mix — a few life-or-death
needles (P1) buried in a large volume of routine worried-well queries (P4).

Deterministic (seeded) so the holdout scoreboard is reproducible.
Run:  python -m app.data.generate_data
Writes: messages.json next to this file.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

SEED = 42
OUT = Path(__file__).parent / "messages.json"

CHANNELS = ["hotline", "eRegister", "email", "whatsapp", "sms"]

# --- P1: immediate physical danger (the needles) -------------------------------
P1 = [
    "We are trapped on the second floor in Hat Yai, water is rising fast and my father can't swim. Please help us now.",
    "My mother is diabetic and we are stranded by the floods, she has run out of insulin since yesterday and is getting confused.",
    "I am stuck on the roof of our guesthouse near Hat Yai market, the water is at the windows and my phone is at 4%.",
    "My 6 year old son got separated from us in the flood evacuation in Songkhla, I cannot find him anywhere, please help.",
    "I'm a Singaporean detained by local police at the border, they won't tell me why and won't let me call anyone. I need consular help.",
    "My husband collapsed and is unconscious, ambulances can't reach us because the roads are flooded. We are near Hat Yai station.",
    "Pregnant and having contractions, stranded by floodwater, no way to get to a hospital. Please send help urgently.",
    "There is fighting near our hotel and we heard explosions, we are hiding in the bathroom, three Singaporeans, scared for our lives.",
    "Elderly couple, my dad is on dialysis and we've missed two sessions because of the floods, he is very weak now.",
    "Our car is being swept by the current with my two kids inside, we are on the highway out of Hat Yai, HELP.",
    "I have a deep cut on my leg from debris, it won't stop bleeding and clinics are all closed or flooded.",
    "We are out of drinking water and food for two days, trapped with an infant, the baby is dehydrated and not responding well.",
    "My friend has severe asthma and her inhaler is finished, she can barely breathe and we cannot get out of the building.",
    "Held at gunpoint earlier, now hiding, do not call my phone it makes noise, message only. Singaporean, need urgent help.",
    "Father had a heart attack, we did CPR, he is breathing but barely, completely cut off by floodwater near Songkhla.",
]

# --- P2: urgent consular action (not yet life-threatening) ---------------------
P2 = [
    "Lost my passport in the flood and the hotel is closed, I'm stranded in Hat Yai with no documents and nowhere to stay tonight.",
    "Stuck at the Thai-Malaysia border crossing which is now closed, no shelter, been here 9 hours with my elderly mother.",
    "My brother flew into Hat Yai two days ago and we've had no contact since the floods started, can you help locate him?",
    "Passport and wallet stolen during the evacuation chaos, I have no money and my flight was cancelled.",
    "I'm hospitalised in Bangkok after an accident, stable now, but I need my family in Singapore notified urgently.",
    "Our tour group of 8 is split up after the evacuation, 3 are missing and not answering, last seen near the bus terminal.",
    "I was briefly detained and released but they kept my passport, I don't know how to get it back. Singaporean citizen.",
    "Stranded at Hat Yai airport since it partially closed, diabetic and my medication is in checked luggage they won't release.",
    "My elderly parents are at a flooded resort with no transport out and their phones are nearly dead, please advise.",
    "Husband missing since he went to move the rental car this morning during the flooding, not reachable, very worried.",
]

# --- P3: assistance request (no immediate risk) --------------------------------
P3 = [
    "My flight via Dubai was cancelled, can you advise how to rebook or what support is available?",
    "We are safe but our hotel flooded, where can Singaporeans find shelter in Hat Yai right now?",
    "Need an official letter confirming the travel disruption so I can claim insurance, how do I get one?",
    "Can someone help me contact my travel insurer? My documents are wet and I can't read the policy number.",
    "I'd like to do a welfare check on my aunt who lives in Songkhla, she is fine but I want to register her details.",
    "Our return flight is delayed indefinitely, are there any arrangements for stranded Singaporeans?",
    "How do I get to the Singapore Embassy in Bangkok from Hat Yai now that the trains are down?",
    "I want to update my eRegister details with my current location in the affected area.",
    "We managed to reach higher ground and are safe, just want to let the Duty Office know and ask what to do next.",
    "Is there a list of approved hotels still operating in Hat Yai for displaced travellers?",
]

# --- P4: routine / worried-well (the bulk volume) ------------------------------
P4_CONCERNS = [
    "Is Hat Yai airport open today?",
    "Are flights from Singapore to Bangkok affected by the floods?",
    "Should I cancel my holiday to Hat Yai next week?",
    "Is it safe to travel to southern Thailand right now?",
    "Are flights transiting through Dubai still operating?",
    "Will my Doha connection be cancelled because of the Middle East situation?",
    "Where can I check the latest travel advisory for Thailand?",
    "My flight is in 5 days, do you think the airport will reopen by then?",
    "Is the train from Hat Yai to Bangkok running?",
    "If I cancel my trip will the government help with the refund?",
    "Is the Songkhla area dangerous for tourists at the moment?",
    "Do I need to register on eRegister if I'm only visiting for the weekend?",
    "Are the highways out of Hat Yai passable for a rental car?",
    "What's the weather forecast for Hat Yai this weekend?",
    "Is it advisable to transit through Dubai next month?",
    "Has the advisory level for Thailand changed?",
    "My hotel cancelled my booking, who is responsible for the cost?",
    "Are there any Singaporeans known to be affected so far?",
    "Should I buy travel insurance before flying to Bangkok?",
    "Is the Middle East airspace fully closed or just delayed?",
]
P4_PREFIX = ["", "Hi, ", "Hello, ", "Good evening, ", "Quick question — ", "Just checking, "]
P4_SUFFIX = ["", " Thanks.", " Please advise.", " Appreciate any info.", " Thank you!"]


def build():
    rng = random.Random(SEED)
    rows = []
    counter = 1

    def add(text, label):
        nonlocal counter
        rows.append({
            "id": f"MSG-{counter:04d}",
            "text": text,
            "channel": rng.choice(CHANNELS),
            "lang": "en",
            "true_label": label,
        })
        counter += 1

    def fill(templates, label, target):
        # Seed with the curated templates, then top up with light prefix/suffix
        # variation (realistic — crisis queues are full of near-duplicates).
        for t in templates:
            add(t, label)
        while sum(1 for r in rows if r["true_label"] == label) < target:
            base = rng.choice(templates)
            add(rng.choice(P4_PREFIX) + base, label)

    for t in P1:
        add(t, "P1")
    fill(P2, "P2", 30)
    fill(P3, "P3", 60)
    # Bulk P4 ~195 via concern x prefix x suffix variation (realistic near-duplicates)
    while sum(1 for r in rows if r["true_label"] == "P4") < 195:
        concern = rng.choice(P4_CONCERNS)
        text = rng.choice(P4_PREFIX) + concern + rng.choice(P4_SUFFIX)
        add(text, "P4")

    # Shuffle arrival order, then assign a streaming offset (surge ~ over 10 min)
    rng.shuffle(rows)
    for i, r in enumerate(rows):
        r["arrival_offset_sec"] = round(i * (600 / len(rows)), 1)

    return rows


def main():
    rows = build()
    OUT.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    counts = {lab: sum(1 for r in rows if r["true_label"] == lab) for lab in ("P1", "P2", "P3", "P4")}
    print(f"wrote {len(rows)} messages to {OUT.name}: {counts}")


if __name__ == "__main__":
    main()
