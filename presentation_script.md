# Presentation Script -- Intelligent Retail Ecosystem
## 8 Minutes | 3 Presenters | 11 Slides

### Presenter Assignments
- **David (D):** Live demo + Architecture + Technical highlights
- **Goncalo (G):** Problem + Value proposition + Solution overview
- **Pedro (P):** Technology stack + Results + Future work + Closing

---

## SLIDE 1: Title (5 seconds)
**[All three standing. Goncalo at laptop, David holding the phone.]**

**G:** "Good morning. We are Group 11 and this is the Intelligent Retail Ecosystem."

**[ADVANCE SLIDE]**

---

## SLIDE 2: Live Demonstration (1 min 30 sec)
**[David holds the phone, screen mirrored to projector if possible. Goncalo advances slides and narrates from the laptop.]**

**G:** "Before we explain anything, let us show you. David is holding a phone running our app. There are three ESP32 boards placed around this room, tracking his position right now."

**D:** *[Opens the app, shows the map with his blue dot]* "As you can see, the system already knows where I am in the room. The blue dot is my live position, updated in real time."

**G:** "Now David will search for a product."

**D:** *[Taps the voice search button]* "Find lobster."

*[Results appear. David taps "Add to queue" on Lobster.]*

**D:** "The system computed the shortest path from my current position to the Lobster shelf. You can see the blue path on the map."

*[David walks toward the shelf. TTS announces: "Turn right."]*

**G:** "Notice the voice directions. The system is announcing turns as David reaches each waypoint."

*[David approaches the target. TTS announces: "You have arrived. Lobster is on the upper shelf."]*

**D:** "That is the full experience. From voice search to guided arrival, under 1.5 seconds of latency."

**G:** "Now let us explain how this works."

**[ADVANCE SLIDE]**

---

## SLIDE 3: The Problem (1 min)
**G:** "The problem we are solving is what we call the information-location gap. Retail inventories know what is in stock, but they fail to communicate exactly where an item is to a person walking through the store."

**G:** "In large supermarkets and furniture stores, shoppers face search fatigue. They spend significant time just wandering between aisles. Staff lose time answering 'where is this product' over and over. And store managers see lower conversion rates because frustrated customers leave without purchasing."

**G:** "Our target users are shoppers who want items fast, staff who need efficient workflows, and managers seeking higher throughput."

**[ADVANCE SLIDE]**

---

## SLIDE 4: Value Proposition (45 sec)
**G:** "Our solution transforms any store into an interactive assistant. Three key values."

**G:** "First, efficiency: the system computes the shortest route across multiple products, reducing time-to-item. Second, accuracy: we achieve 1 to 1.5 metre positioning precision with shelf-level guidance. Third, accessibility: voice search and turn-by-turn audio make navigation hands-free, which benefits all users, including those with visual impairments."

**G:** "Importantly, this requires no specialised hardware. Any Android phone and three ESP32 boards at five euros each."

**[ADVANCE SLIDE]**

---

## SLIDE 5: Solution Overview (45 sec)
**P:** "The user experience has four steps. First, search: say 'find lobster' or type it. We use native Android speech recognition with fuzzy text matching as fallback."

**P:** "Second, locate: three ESP32 gateways capture the phone's Bluetooth signal. The phone's IMU provides steps and heading. These are fused through a Kalman filter on the backend."

**P:** "Third, navigate: A-star pathfinding computes the optimal route on a grid. For multiple products, a nearest-neighbour heuristic with 2-opt refinement orders the shopping list."

**P:** "Fourth, guide: text-to-speech announces turns at every waypoint, and upon arrival, it tells the user which shelf level the product is on."

**[ADVANCE SLIDE]**

---

## SLIDE 6: Architecture (1 min)
**D:** "Here is the system architecture. Three layers."

**D:** "At the edge, three ESP32 boards continuously scan for BLE advertisements. They filter by our app's IRE prefix, so nearby headphones or smartwatches are ignored. Valid readings are published to MQTT."

**D:** "The processing layer is a FastAPI server. It receives RSSI via MQTT, smooths it with an exponential moving average, and trilaterates the position using weighted least-squares. Simultaneously, IMU data arrives via WebSocket. A linear Kalman filter with state x, y, velocity-x, velocity-y fuses both sources."

**D:** "On the client side, a Kotlin Android app hosts a React frontend in a WebView. It broadcasts a unique BLE session ID and streams IMU data at ten hertz. The WebSocket connection has automatic reconnection with a two-second heartbeat."

**[ADVANCE SLIDE]**

---

## SLIDE 7: Technical Highlights (1 min)
**D:** "Two technical areas worth highlighting."

**D:** "For localisation: BLE alone gave us roughly 3.5 metres of error, consistent with the literature. By adding IMU fusion through the Kalman filter, where the process noise scales with delta-t and measurement noise adapts to signal strength, we brought this down to 1 to 1.5 metres."

**D:** "For navigation: A-star runs on a 40 by 20 grid at 0.25 metre resolution, with shelf footprints marked as obstacles. Douglas-Peucker simplifies the path for cleaner directions. For multi-product shopping lists, a TSP heuristic with 2-opt improvement finds the shortest total route. The text-to-speech engine has a two-second cooldown between announcements to avoid overwhelming the user."

**D:** "End-to-end measured latency: 1,490 milliseconds, just within our 1,500 millisecond target."

**[ADVANCE SLIDE]**

---

## SLIDE 8: Technology Stack (30 sec)
**P:** "A quick overview of our stack. The mobile app is native Kotlin hosting a React WebView. The backend is Python with FastAPI and SQLite. Communication uses MQTT for hardware and WebSockets for the app. Voice input uses Android's native SpeechRecognizer, and voice output uses the browser's SpeechSynthesis API. Total hardware cost: approximately fifteen euros for three ESP32 boards."

**[ADVANCE SLIDE]**

---

## SLIDE 9: Results (45 sec)
**P:** "Our results against the initial requirements. Six of eight fully satisfied, two partially."

**P:** "Precision: satisfied, at 1 to 1.5 metres with IMU fusion. Stability: partially satisfied -- marker jumps are significantly reduced but not entirely eliminated, particularly near metallic obstacles. Latency: satisfied at 1,490 milliseconds."

**P:** "For user interaction: voice and text search both work reliably, route optimisation with TSP and 2-opt is functional, and A-star wayfinding with TTS directions is complete. Micro-navigation is partially satisfied -- we provide shelf-level guidance via TTS but did not implement computer vision for on-shelf product identification."

**P:** "Platform: satisfied. Tested on a Samsung Galaxy A32 running Android 12."

**[ADVANCE SLIDE]**

---

## SLIDE 10: Backup Demo Plan (skip if live demo succeeded)
**[Only show this slide if the live demo failed. Otherwise, skip it.]**

**G:** "In case our live demo encountered issues, here is a recorded walkthrough."

*[Play the pre-recorded video. Goncalo narrates over it briefly.]*

**[ADVANCE SLIDE]**

---

## SLIDE 11: Future Work and Closing (30 sec)
**P:** "For future work: adding more ESP32 gateways would tighten the triangulation. Optimising the beacon scan cycle below one second would improve latency. Computer vision integration would enable precise on-shelf identification. And cross-platform iOS support would broaden reach."

**P:** "To summarise: with fifteen euros of hardware and any Android phone, we built a complete indoor navigation system. 1 to 1.5 metre accuracy, voice-guided, hands-free, with optimised multi-product routing and 1.49 seconds of end-to-end latency."

**P:** "We turned a store into an intelligent assistant. Thank you."

**[All three available for questions.]**

---

## Timing Summary

| Section | Presenter | Duration |
|---------|-----------|----------|
| Title | G | 5 sec |
| Live Demo | D + G | 1:30 |
| Problem | G | 1:00 |
| Value Proposition | G | 0:45 |
| Solution Overview | P | 0:45 |
| Architecture | D | 1:00 |
| Technical Highlights | D | 1:00 |
| Technology Stack | P | 0:30 |
| Results | P | 0:45 |
| Future + Closing | P | 0:30 |
| **Total** | | **~7:50** |

Buffer of ~10 seconds for slide transitions and unexpected pauses.

---

## Pre-Demo Checklist

1. ESP32 boards powered on and connected to hotspot
2. Backend running (`uvicorn app.main:app --port 8000`)
3. Frontend running (`npm run dev` on 0.0.0.0:3000)
4. Mosquitto broker running
5. Phone app open, BLE advertising active, position visible on map
6. Phone volume up (for TTS)
7. Screen mirroring set up (if available)
8. Backup demo video loaded and ready to play
9. Products seeded in database (lobster available for demo)
10. Store layout matching the demo room's shelf positions
