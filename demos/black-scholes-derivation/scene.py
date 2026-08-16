from manim import *
from math import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.gtts import GTTSService


class GenScene(VoiceoverScene):
    def construct(self):
        self.set_speech_service(GTTSService(lang="en"))

        # ---------------- 1. Concept Definition ----------------
        title = Tex("The Black-Scholes Partial Differential Equation")
        title.scale_to_fit_width(config.frame_width * 0.9).to_edge(UP)

        defn = Tex(
            "A derivative's price must obey a no-arbitrage law when the stock moves randomly."
        )
        defn.scale_to_fit_width(config.frame_width * 0.85).next_to(title, DOWN, buff=0.8)

        with self.voiceover(text="Let us derive the Black-Scholes equation step by step, starting from the idea of no arbitrage.") as tracker:
            self.play(Write(title), run_time=tracker.duration)

        with self.voiceover(text="A derivative price must obey a no arbitrage law, even though the underlying stock moves randomly.") as tracker:
            self.play(FadeIn(defn, shift=UP), run_time=tracker.duration)

        self.wait(0.5)
        self.play(FadeOut(defn), FadeOut(title))

        # ---------------- 2. Step 1: The stock model ----------------
        s1 = Tex("Step 1: The stock follows geometric Brownian motion")
        s1.scale_to_fit_width(config.frame_width * 0.8).to_edge(UP)

        sde = MathTex(r"dS = \mu S \, dt + \sigma S \, dW")
        sde.scale(1.2).next_to(s1, DOWN, buff=1.0)

        legend = Tex("drift term plus random shock term")
        legend.scale(0.8).next_to(sde, DOWN, buff=0.8)

        with self.voiceover(text="Step one. The stock price follows geometric Brownian motion, with a drift term and a random shock term.") as tracker:
            self.play(Write(s1), FadeIn(sde), run_time=tracker.duration)

        with self.voiceover(text="Here mu is the expected return, sigma the volatility, and d W a Wiener increment.") as tracker:
            self.play(FadeIn(legend), run_time=tracker.duration)

        self.wait(0.4)
        self.play(FadeOut(s1), FadeOut(sde), FadeOut(legend))

        # ---------------- 3. Step 2: Ito's Lemma ----------------
        s2 = Tex("Step 2: Apply Ito's Lemma to the option value V of S and t")
        s2.scale_to_fit_width(config.frame_width * 0.85).to_edge(UP)

        ito = MathTex(
            r"dV = \left( \frac{\partial V}{\partial t}"
            r"+ \mu S \frac{\partial V}{\partial S}"
            r"+ \frac{1}{2}\sigma^2 S^2 \frac{\partial^2 V}{\partial S^2} \right) dt"
            r"+ \sigma S \frac{\partial V}{\partial S} dW"
        )
        ito.scale_to_fit_width(config.frame_width * 0.9).next_to(s2, DOWN, buff=1.0)

        with self.voiceover(text="Step two. Apply Ito's Lemma to the option value V, a function of the stock price and time.") as tracker:
            self.play(Write(s2), run_time=tracker.duration)

        with self.voiceover(text="Ito adds a second order term, one half sigma squared S squared times the second derivative of V.") as tracker:
            self.play(FadeIn(ito), run_time=tracker.duration)

        self.wait(0.4)
        self.play(FadeOut(s2), FadeOut(ito))

        # ---------------- 4. Step 3: Hedged portfolio ----------------
        s3 = Tex("Step 3: Build a delta hedged portfolio")
        s3.scale_to_fit_width(config.frame_width * 0.7).to_edge(UP)

        port = MathTex(r"\Pi = V - \frac{\partial V}{\partial S}\, S")
        port.scale(1.1).next_to(s3, DOWN, buff=0.8)

        dport = MathTex(
            r"d\Pi = \left( \frac{\partial V}{\partial t}"
            r"+ \frac{1}{2}\sigma^2 S^2 \frac{\partial^2 V}{\partial S^2} \right) dt"
        )
        dport.scale_to_fit_width(config.frame_width * 0.75).next_to(port, DOWN, buff=0.8)

        note = Tex("The random d W terms cancel exactly.")
        note.scale(0.8).next_to(dport, DOWN, buff=0.6)

        with self.voiceover(text="Step three. Hold one option and short delta shares of stock, where delta is the derivative of V with respect to S.") as tracker:
            self.play(Write(s3), FadeIn(port), run_time=tracker.duration)

        with self.voiceover(text="The random terms cancel exactly, so the portfolio change is completely deterministic.") as tracker:
            self.play(FadeIn(dport), FadeIn(note), run_time=tracker.duration)

        self.wait(0.4)
        self.play(FadeOut(s3), FadeOut(port), FadeOut(dport), FadeOut(note))

        # ---------------- 5. Step 4: No arbitrage and the PDE ----------------
        s4 = Tex("Step 4: A riskless portfolio must earn the riskless rate")
        s4.scale_to_fit_width(config.frame_width * 0.85).to_edge(UP)

        arb = MathTex(r"d\Pi = r\,\Pi\, dt")
        arb.scale(1.2).next_to(s4, DOWN, buff=0.7)

        pde = MathTex(
            r"\frac{\partial V}{\partial t}"
            r"+ \frac{1}{2}\sigma^2 S^2 \frac{\partial^2 V}{\partial S^2}"
            r"+ rS \frac{\partial V}{\partial S} - rV = 0"
        )
        pde.scale_to_fit_width(config.frame_width * 0.85).next_to(arb, DOWN, buff=0.9)
        box = SurroundingRectangle(pde, color=YELLOW, buff=0.25)

        with self.voiceover(text="Step four. Since the portfolio is riskless, it must earn the risk free rate r, or arbitrage would exist.") as tracker:
            self.play(Write(s4), FadeIn(arb), run_time=tracker.duration)

        with self.voiceover(text="Equating the two expressions gives the Black-Scholes partial differential equation. Notice that mu has vanished.") as tracker:
            self.play(FadeIn(pde), Create(box), run_time=tracker.duration)

        self.wait(0.4)
        self.play(FadeOut(s4), FadeOut(arb), FadeOut(pde), FadeOut(box))

        # ---------------- 6. Chart ----------------
        chart_title = Tex("Call value versus payoff at expiry")
        chart_title.scale_to_fit_width(config.frame_width * 0.7).to_edge(UP)

        axes = Axes(
            x_range=[50, 150, 25],
            y_range=[0, 55, 25],
            x_length=8,
            y_length=4,
            axis_config={"include_numbers": True},
        )
        labels = axes.get_axis_labels(x_label=Tex("S"), y_label=Tex("Value"))

        payoff = axes.plot(lambda x: max(x - 100.0, 0.0), color=BLUE)

        def bs_call(S):
            K, r, sig, T = 100.0, 0.05, 0.2, 1.0
            d1 = (log(S / K) + (r + 0.5 * sig * sig) * T) / (sig * sqrt(T))
            d2 = d1 - sig * sqrt(T)
            N = lambda x: 0.5 * (1 + erf(x / sqrt(2)))
            return S * N(d1) - K * exp(-r * T) * N(d2)

        curve = axes.plot(bs_call, color=YELLOW)

        group = VGroup(axes, labels, payoff, curve).scale(0.7).to_edge(DOWN)

        with self.voiceover(text="Solving the equation for a call gives a smooth curve that always sits above the kinked payoff at expiry.") as tracker:
            self.play(Write(chart_title), Create(group), run_time=tracker.duration)

        self.wait(0.4)
        self.play(FadeOut(chart_title), FadeOut(group))

        # ---------------- 7. Case study ----------------
        case = Tex("Case study: one year at the money call")
        case.scale_to_fit_width(config.frame_width * 0.7).to_edge(UP)

        line1 = MathTex(r"S = 100,\ K = 100,\ r = 0.05,\ \sigma = 0.20,\ T = 1")
        line2 = MathTex(r"d_1 = \frac{0 + (0.05 + 0.02)(1)}{0.20} = 0.35")
        line3 = MathTex(r"d_2 = 0.35 - 0.20 = 0.15")
        line4 = MathTex(r"C = 100(0.6368) - 95.12(0.5596) \approx 10.45")

        steps = VGroup(line1, line2, line3, line4).arrange(DOWN, buff=0.45)
        steps.scale_to_fit_width(config.frame_width * 0.75).next_to(case, DOWN, buff=0.7)

        with self.voiceover(text="A numerical case. Stock one hundred, strike one hundred, rate five percent, volatility twenty percent, one year.") as tracker:
            self.play(Write(case), FadeIn(line1), run_time=tracker.duration)

        with self.voiceover(text="We compute d one equals zero point three five, and d two equals zero point one five.") as tracker:
            self.play(FadeIn(line2), FadeIn(line3), run_time=tracker.duration)

        with self.voiceover(text="Plugging into the formula gives a call value of about ten dollars forty five cents.") as tracker:
            self.play(FadeIn(line4), run_time=tracker.duration)

        self.wait(0.4)
        self.play(FadeOut(case), FadeOut(steps))

        # ---------------- 8. Summary ----------------
        sum_title = Tex("Key takeaways")
        sum_title.scale_to_fit_width(config.frame_width * 0.4).to_edge(UP)

        b1 = Tex("1. Ito's Lemma creates the second order volatility term.")
        b2 = Tex("2. Delta hedging removes all randomness.")
        b3 = Tex("3. No arbitrage forces the riskless rate r into the equation.")
        b4 = Tex("Warning: the drift mu never appears. Risk preferences drop out.")
        bullets = VGroup(b1, b2, b3, b4).arrange(DOWN, aligned_edge=LEFT, buff=0.5)
        bullets.scale_to_fit_width(config.frame_width * 0.85).next_to(sum_title, DOWN, buff=0.7)
        b4.set_color(YELLOW)

        with self.voiceover(text="To summarize. Ito's Lemma creates the second order term, and delta hedging removes all randomness.") as tracker:
            self.play(FadeIn(b1), FadeIn(b2), Write(sum_title), run_time=tracker.duration)

        with self.voiceover(text="No arbitrage then forces the riskless rate into the equation. Remember, the drift mu never appears.") as tracker:
            self.play(FadeIn(b3), FadeIn(b4), run_time=tracker.duration)

        self.wait(1)