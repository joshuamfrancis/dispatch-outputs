# Transistors as Switches with Microcontrollers

---

## INTRO

Hey everyone, welcome back.

Today we're talking about one of the most practical skills in electronics —

using a transistor as a switch, controlled by a microcontroller.

If you've ever wanted to turn on a motor, a relay, a high-powered LED, or any load

that draws more current than your microcontroller can safely supply —

this is the technique you need.

Let's get into it.

---

## THE PROBLEM — Why You Can't Drive Loads Directly

So here's the situation.

You've got a microcontroller — an Arduino, an ESP32, a Raspberry Pi Pico — doesn't matter which one.

The GPIO pins on these boards can output a signal, usually 3.3 or 5 volts.

But here's the catch.

Most microcontroller GPIO pins can only source or sink around 20 to 40 milliamps of current.

That's enough to blink an LED.

But a DC motor? A solenoid? A 12-volt fan? A string of LEDs?

Those loads can pull hundreds of milliamps — sometimes amps.

Trying to drive them directly from a GPIO pin will either give you unreliable behaviour,

or — worst case — damage your microcontroller permanently.

That's where the transistor comes in.

---

## WHAT IS A TRANSISTOR — The Quick Version

A transistor is a three-terminal semiconductor device.

The three terminals are called the **Base**, the **Collector**, and the **Emitter** —

for a bipolar junction transistor, or BJT.

Think of it like a valve.

A small current flowing into the Base

controls whether a much larger current can flow from the Collector to the Emitter.

Your microcontroller provides that small Base current.

The transistor does the heavy lifting for the load.

That's the core idea. Small signal in — big current switched.

---

## NPN vs PNP — Which One Do We Use?

There are two flavours of BJT: NPN and PNP.

For switching a load between the transistor and ground — called a **low-side switch** —

we use an **NPN transistor**.

When the Base goes HIGH, current flows from Collector to Emitter, completing the circuit.

When the Base goes LOW, the transistor is off, and the load has no path to ground.

PNP transistors work the opposite way and are used in high-side switching —

but for most microcontroller projects, NPN low-side is what you want.

A classic general-purpose NPN to start with is the **2N2222** or the **BC547**.

For higher currents, look at the **TIP120** — a Darlington transistor —

which can handle up to 5 amps.

---

## THE CIRCUIT — How to Wire It Up

Here's how the circuit works.

Your load — let's say a DC motor — sits between your positive supply voltage and the Collector.

The Emitter goes to ground.

The Base connects to your GPIO pin through a **base resistor**.

That resistor is critical. It limits the current going into the Base

so you don't exceed the GPIO pin's current rating or damage the transistor.

A typical value is **1 kilohm** for a 5V system, or **470 ohms** for 3.3V.

You calculate it like this:

Base resistor equals V-GPIO minus V-BE, divided by I-Base.

V-BE is typically 0.7 volts for a silicon BJT.

I-Base should be at least one tenth of the load current divided by the transistor's gain — hFE.

Most general-purpose NPN transistors have an hFE between 100 and 300,

so a 1K resistor covers a wide range of common loads.

One more component you must not skip —

a **flyback diode**, also called a freewheeling diode, across your load.

If the load is inductive — a motor, a relay coil, a solenoid —

it stores energy in its magnetic field.

When the transistor switches off and the current stops suddenly,

that energy has to go somewhere.

Without a diode, it creates a voltage spike that can destroy your transistor instantly.

Use a **1N4007** or **1N4148**, placed with the cathode toward the positive supply.

It just sits there doing nothing — until it saves your circuit.

---

## THE CODE — Controlling It from Your Microcontroller

From the software side, this is as simple as it gets.

Your GPIO pin is set as an output.

When you write HIGH to it, the transistor turns on, and your load gets power.

When you write LOW, the transistor turns off.

Here's a quick Arduino example —

```cpp
const int transistorPin = 9;

void setup() {
  pinMode(transistorPin, OUTPUT);
}

void loop() {
  digitalWrite(transistorPin, HIGH);  // turn load ON
  delay(2000);
  digitalWrite(transistorPin, LOW);   // turn load OFF
  delay(2000);
}
```

And if you use a PWM-capable pin, you can do even more —

you can control the speed of a motor, or dim a high-power LED,

by varying the duty cycle with `analogWrite`.

```cpp
analogWrite(transistorPin, 128);  // ~50% power
```

The transistor switches on and off thousands of times per second.

The load sees an average voltage proportional to the duty cycle.

That's PWM — pulse width modulation — and it's incredibly useful.

---

## MOSFETs — The Better Switch for Most Cases

Now, before we wrap up — a quick word on MOSFETs.

The BJT transistor is great for learning the concept,

but in modern electronics, the **MOSFET** — Metal-Oxide-Semiconductor Field-Effect Transistor —

is often the preferred switch for higher-power applications.

The key difference: a MOSFET is voltage-controlled, not current-controlled.

The Gate needs a voltage to switch — it draws almost no current.

That means almost zero load on your GPIO pin.

A popular choice for 5V and 3.3V microcontrollers is the **IRLZ44N** or the **2N7000**.

These are logic-level MOSFETs, meaning they switch fully on with the 3.3 or 5 volts your GPIO provides.

The wiring is similar — Gate to GPIO through a resistor,

Drain to the load, Source to ground.

Flyback diode still applies for inductive loads.

If you're switching anything above an amp, strongly consider a MOSFET over a BJT.

---

## COMMON MISTAKES TO AVOID

Let's quickly run through the mistakes I see most often.

**Number one** — forgetting the base resistor.

Without it, you're dumping the full GPIO output current into the Base.

That can damage the pin and the transistor.

**Number two** — skipping the flyback diode on inductive loads.

I'll say it again because it matters.

Motors, relays, solenoids — always add the diode. No exceptions.

**Number three** — ground loops.

Your microcontroller ground and your load power supply ground must be connected together.

If they're floating relative to each other, the transistor can't switch properly.

**Number four** — using a non-logic-level MOSFET with 3.3V.

A standard MOSFET like the IRF540 needs 10 volts on the Gate to switch fully on.

At 3.3V it will be in a partial-on state, getting hot and wasting power.

Always check the datasheet for Vgs threshold.

---

## REAL WORLD APPLICATIONS

So where does this actually show up?

Relay modules — the transistor inside switches the relay coil.

Motor driver boards — H-bridges use transistors or MOSFETs in pairs to control direction and speed.

LED drivers — high-power LEDs for lighting or photography rigs.

Solenoid valves — for water, air, or pneumatics in automation projects.

Heating elements — controlling a heating coil with PWM for temperature regulation.

Any time you need a microcontroller to control something that demands more power

than the GPIO can provide — a transistor or MOSFET is the answer.

---

## WRAP UP

To summarise —

Microcontroller GPIO pins have limited current output.

A transistor acts as an electrically controlled switch,

letting a small GPIO signal control a much larger load current.

Use an NPN BJT for low-side switching, with a base resistor and flyback diode.

Use a logic-level N-channel MOSFET for higher currents and efficiency.

And always tie your grounds together.

That's it for today.

If this was helpful, hit like and subscribe —

and drop a comment letting me know what load you're switching in your project.

I'll see you in the next one.

---

*Script end.*
