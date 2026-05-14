import React from 'react';

export function OperatingMap() {
  return (
    <div className="bg-[#f4f1ea] text-[#1a1a1a] font-serif min-h-screen px-6 py-4 flex flex-col items-center">
      <div className="w-full max-w-[1400px]">
        {/* Masthead */}
        <div className="border-b-2 border-t-2 border-black/80 py-4 mb-8 flex flex-col items-center relative">
          <div className="absolute top-4 left-0 text-[10px] tracking-widest font-sans font-semibold uppercase text-black/60">
            EST. WHEN YOU FIRST CONNECTED
          </div>
          <div className="absolute top-4 right-0 text-[10px] tracking-widest font-sans font-semibold uppercase text-black/60">
            PRICE: ONE DECISION
          </div>
          <div className="text-[10px] tracking-widest font-sans font-semibold uppercase text-black/60 mb-2">
            EDITION No. 142 · WED · 13 MAY 2026 · 09:14 IST
          </div>
          <h1 className="text-5xl md:text-6xl lg:text-7xl font-bold tracking-tight mb-2">
            The Cotton-Co Daily
          </h1>
          <p className="text-sm italic text-black/70">
            "An operating brief, filed by your data — not your team." - sources: shopify - excel - mailchimp - stripe
          </p>
        </div>

        {/* Columns */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 lg:gap-12 divide-y md:divide-y-0 md:divide-x divide-black/20">
          
          {/* Column 1 */}
          <div className="flex flex-col gap-6 md:pr-4 lg:pr-6">
            <section>
              <div className="text-[#d95d39] text-[10px] font-sans font-semibold tracking-widest uppercase mb-2">
                OPERATIONS - LEAD
              </div>
              <h2 className="text-3xl font-bold leading-tight mb-3 tracking-tight">
                Bangalore quietly outpaces Mumbai three to one — and the cause isn't what you'd guess
              </h2>
              <p className="text-sm italic text-black/70 mb-4 leading-relaxed">
                Same products. Same campaigns. The difference, by every signal we crossed, is delivery speed.
              </p>
              
              <div className="text-sm leading-relaxed text-black/80">
                <span className="float-left text-5xl font-bold leading-[0.8] mr-2 mt-1">F</span>
                or weeks the founder team has split marketing budget evenly between the two cities, and the orders pull suggested the spend was working. The <span className="italic">reorders</span> pull tells a different story. Bangalore customers see their parcels in <strong className="font-semibold text-black">1.8 days on average</strong>, Mumbai customers wait <strong className="font-semibold text-black">3.6</strong>. Mailchimp open rates trail in step — 64% in BLR, 38% in MUM. Product mix is identical.
              </div>
              <p className="text-sm italic text-black/80 mt-4 font-semibold">
                Baseflo's reading: delivery speed is the gate that lets every other channel work.
              </p>
            </section>

            {/* Chart */}
            <div className="mt-6 mb-8 flex flex-col items-center">
              <div className="text-[10px] font-sans text-black/50 mb-2 italic">reorder rate - 30d, by city</div>
              <div className="flex items-end gap-6 h-24 border-b border-black/30 pb-1 px-4">
                <div className="flex flex-col items-center gap-1">
                  <span className="text-[10px] font-sans">42%</span>
                  <div className="w-12 bg-[#d95d39] border border-black/80" style={{ height: '80px' }}></div>
                  <span className="text-[10px] font-sans font-semibold">BLR</span>
                </div>
                <div className="flex flex-col items-center gap-1">
                  <span className="text-[10px] font-sans">13%</span>
                  <div className="w-12 bg-black/60" style={{ height: '24px' }}></div>
                  <span className="text-[10px] font-sans font-semibold">PUN</span>
                </div>
                <div className="flex flex-col items-center gap-1">
                  <span className="text-[10px] font-sans">14%</span>
                  <div className="w-12 bg-black/60" style={{ height: '26px' }}></div>
                  <span className="text-[10px] font-sans font-semibold">DEL</span>
                </div>
                <div className="flex flex-col items-center gap-1">
                  <span className="text-[10px] font-sans">10%</span>
                  <div className="w-12 bg-black/60" style={{ height: '18px' }}></div>
                  <span className="text-[10px] font-sans font-semibold">MUM</span>
                </div>
              </div>
              <div className="text-[9px] font-sans text-black/40 mt-2 italic text-center max-w-[200px]">
                Source: Shopify orders joined to customer city via shipping address - 30-day rolling
              </div>
            </div>

            {/* To Do Box */}
            <div className="border border-black/40 p-4 bg-white/40 mt-auto">
              <div className="text-[#d95d39] text-[10px] font-sans font-semibold tracking-widest uppercase mb-2">
                TO DO TODAY
              </div>
              <h3 className="font-bold text-sm mb-1 leading-snug">
                Run a BLR look-alike on Meta. Pilot a faster MUM courier.
              </h3>
              <p className="text-[11px] font-sans text-black/60 italic mb-4">
                Reach ~860 prospects · pilot 200 MUM orders for 2 weeks.
              </p>
              <div className="flex gap-2">
                <button className="bg-[#d95d39] text-white text-[11px] font-sans font-semibold px-3 py-1.5 rounded-sm border border-black/80 hover:bg-[#c45332]">
                  queue both
                </button>
                <button className="bg-transparent text-black text-[11px] font-sans font-semibold px-3 py-1.5 rounded-sm border border-black/80 border-dashed hover:bg-black/5">
                  just the ad
                </button>
              </div>
            </div>
          </div>

          {/* Column 2 */}
          <div className="flex flex-col gap-10 md:px-4 lg:px-6 pt-6 md:pt-0">
            <section>
              <div className="text-[#d95d39] text-[10px] font-sans font-semibold tracking-widest uppercase mb-2">
                INVENTORY
              </div>
              <h2 className="text-2xl font-bold leading-tight mb-2 tracking-tight">
                Fourteen products only your offline customers know about
              </h2>
              <p className="text-sm italic text-black/70 mb-4 leading-relaxed">
                Moved units in the shop. Online they remain ghosts.
              </p>
              <p className="text-sm leading-relaxed text-black/80 mb-4">
                Fourteen SKUs have <strong className="font-semibold text-black">zero</strong> online orders and <strong className="font-semibold text-black">412</strong> offline buyers in the last thirty days. Customers who walked in for these don't know you sell them on the site.
              </p>
              
              <div className="border border-black/40 p-4 bg-white/40 mb-2">
                <div className="text-[#d95d39] text-[10px] font-sans font-semibold tracking-widest uppercase mb-3">
                  READ THE LIST
                </div>
                <div className="font-mono text-[11px] text-black/80 flex flex-col gap-1.5">
                  <div className="flex justify-between"><span>linen-set-L</span> <span>· 38 offline</span></div>
                  <div className="flex justify-between"><span>henley-olive</span> <span>· 29 offline</span></div>
                  <div className="flex justify-between"><span>shorts-32</span> <span>· 22 offline</span></div>
                  <div className="text-black/50 mt-1 italic">+ 11 more - open list →</div>
                </div>
              </div>
            </section>

            <section>
              <div className="text-[#d95d39] text-[10px] font-sans font-semibold tracking-widest uppercase mb-2">
                QUALITY
              </div>
              <h2 className="text-xl font-bold leading-tight mb-3 tracking-tight">
                The Olive variant is dragging down a strong year for the Cotton Tee
              </h2>
              <p className="text-sm leading-relaxed text-black/80 mb-6">
                Reviews score the Olive at <strong className="font-semibold text-black">2.1 stars</strong>; other variants average <strong className="font-semibold text-black">4.5</strong>. Twenty-three buyers owed a replacement.
              </p>
              <button className="w-full bg-[#d95d39] text-white text-[11px] font-sans font-semibold px-4 py-2 rounded-sm border border-black/80 hover:bg-[#c45332] text-left">
                email 23 buyers · replacement
              </button>
            </section>
          </div>

          {/* Column 3 */}
          <div className="flex flex-col gap-10 md:px-4 lg:px-6 pt-6 md:pt-0">
            <section>
              <div className="text-[#d95d39] text-[10px] font-sans font-semibold tracking-widest uppercase mb-2">
                CUSTOMERS
              </div>
              <h2 className="text-2xl font-bold leading-tight mb-2 tracking-tight">
                Forty-seven people read your emails but never buy
              </h2>
              <p className="text-sm italic text-black/70 mb-4 leading-relaxed">
                Engaged. Quiet. Worth ₹1.13L in lifetime value.
              </p>
              <p className="text-sm leading-relaxed text-black/80 mb-4">
                These forty-seven opened the last three Mailchimp sends and haven't ordered in sixty days. They want to buy. They aren't. Intent without conversion is usually a price-or-timing problem.
              </p>
              
              <div className="border border-black/80 p-4 bg-white/60 mb-4 shadow-[2px_2px_0px_rgba(0,0,0,1)]">
                <p className="text-[13px] italic text-black/90 mb-2">
                  "Intent without conversion needs a small nudge, not a clever campaign."
                </p>
                <div className="text-[9px] font-sans font-bold tracking-widest text-black/50 uppercase">
                  — BASEFLO
                </div>
              </div>

              <div className="flex flex-col gap-1.5 border border-black/80 p-1.5 shadow-[2px_2px_0px_rgba(0,0,0,1)]">
                <button className="w-full bg-[#d95d39] text-white text-[11px] font-sans font-semibold px-3 py-1.5 rounded-sm border border-black/80 hover:bg-[#c45332] text-left">
                  send 12% coupon · 7d
                </button>
                <button className="w-full bg-transparent text-black text-[11px] font-sans font-semibold px-3 py-1.5 rounded-sm border border-black/80 border-dashed hover:bg-black/5 text-left">
                  move 47 to sales call list
                </button>
              </div>
            </section>

            <section>
              <div className="text-[#d95d39] text-[10px] font-sans font-semibold tracking-widest uppercase mb-2">
                OPS - URGENT
              </div>
              <h2 className="text-xl font-bold leading-tight mb-3 tracking-tight">
                Five SKUs will run out before a reorder can land
              </h2>
              <p className="text-sm leading-relaxed text-black/80 mb-6">
                Top-five movers have eight days of cover. Supplier needs fourteen. The six-day gap is the most consequential number on this page.
              </p>
              <button className="w-full bg-[#d95d39] text-white text-[11px] font-sans font-semibold px-4 py-2 rounded-sm border border-black/80 hover:bg-[#c45332] text-left">
                place reorder today
              </button>
            </section>
          </div>

          {/* Column 4 */}
          <div className="flex flex-col gap-10 md:pl-4 lg:pl-6 pt-6 lg:pt-0">
            <section>
              <div className="text-[#d95d39] text-[10px] font-sans font-semibold tracking-widest uppercase mb-4 border-b border-[#d95d39]/30 pb-2">
                BY THE NUMBERS
              </div>
              
              <div className="flex flex-col gap-4">
                <div className="flex justify-between items-baseline border-b border-black/10 pb-2">
                  <span className="text-sm text-black/80">Customers</span>
                  <div className="text-right">
                    <div className="font-bold text-lg font-sans">4,829</div>
                    <div className="text-[9px] text-[#d95d39] font-sans">↑ 184 this week</div>
                  </div>
                </div>

                <div className="flex justify-between items-baseline border-b border-black/10 pb-2">
                  <span className="text-sm text-black/80">Orders · 30d</span>
                  <div className="text-right">
                    <div className="font-bold text-lg font-sans">1,247</div>
                    <div className="text-[9px] text-green-700 font-sans">↑ 12% YoY</div>
                  </div>
                </div>

                <div className="flex justify-between items-baseline border-b border-black/10 pb-2">
                  <span className="text-sm text-black/80">Revenue · 30d</span>
                  <div className="text-right">
                    <div className="font-bold text-lg font-sans">₹18.4L</div>
                    <div className="text-[9px] text-green-700 font-sans">↑ 15% YoY</div>
                  </div>
                </div>

                <div className="flex justify-between items-baseline border-b border-black/10 pb-2">
                  <span className="text-sm text-black/80">Reorder rate</span>
                  <div className="text-right">
                    <div className="font-bold text-lg font-sans">24%</div>
                    <div className="text-[9px] text-black/50 font-sans">↑ 2 pp · this month</div>
                  </div>
                </div>

                <div className="flex justify-between items-baseline border-b border-black/10 pb-2">
                  <span className="text-sm text-black/80">Avg order value</span>
                  <div className="text-right">
                    <div className="font-bold text-lg font-sans">₹1,470</div>
                    <div className="text-[9px] text-red-700 font-sans">↓ 3% · w-o-w</div>
                  </div>
                </div>

                <div className="flex justify-between items-baseline">
                  <span className="text-sm text-black/80">Engaged-dormant</span>
                  <div className="text-right">
                    <div className="font-bold text-lg font-sans">47</div>
                    <div className="text-[9px] text-black/50 font-sans">cohort identified today</div>
                  </div>
                </div>
              </div>
            </section>

            <section>
              <div className="text-[#d95d39] text-[10px] font-sans font-semibold tracking-widest uppercase mb-4 border-b border-[#d95d39]/30 pb-2">
                WHAT CHANGED OVERNIGHT
              </div>
              <ul className="text-xs text-black/80 space-y-3 font-sans list-disc pl-4 marker:text-black/40">
                <li>12 new Shopify orders since last edition</li>
                <li>Mailchimp open rate dropped <strong>6 pp</strong> this week</li>
                <li>Linen Set crossed 8-day cover threshold</li>
                <li>One new review - 5★ - Hoodie Black</li>
              </ul>
            </section>
          </div>

        </div>
      </div>
    </div>
  );
}
