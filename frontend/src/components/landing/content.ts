// Landing-page copy. Every number and every named incident must point to a source in
// SOURCES; scenarios that are not real cases are marked `illustrative`.

export type SourceId =
  | "shorts3min"
  | "contentId2025"
  | "strikes"
  | "ascify25"
  | "ccpa"
  | "metaUnoriginal"
  | "ytInauthentic"
  | "carryBI"
  | "carryQuint"
  | "memePurge"
  | "baapOfChart"
  | "enderman";

export const SOURCES: Record<SourceId, { label: string; url: string }> = {
  shorts3min: {
    label: "YouTube Help: Understand three-minute YouTube Shorts",
    url: "https://support.google.com/youtube/answer/15424877",
  },
  contentId2025: {
    label: "TorrentFreak: YouTube processed 2.5 billion Content ID claims in 2025 (YouTube Copyright Transparency Report)",
    url: "https://torrentfreak.com/youtube-processed-2-5-billion-content-id-copyright-claims-in-2025/",
  },
  strikes: {
    label: "YouTube Help: Understand copyright strikes",
    url: "https://support.google.com/youtube/answer/2814000",
  },
  ascify25: {
    label: "afaqs: ASCI Annual Complaints Report 2024-25",
    url: "https://www.afaqs.com/news/advertising/offshore-betting-and-realty-emerge-as-the-most-violative-sectors-asci-9314896",
  },
  ccpa: {
    label: "Digit: CCPA endorsement guidelines for influencers (Jan 2023)",
    url: "https://www.digit.in/news/general/influencers-may-be-liable-to-pay-50-lakhs-for-not-disclosing-sponsorships-66917.html",
  },
  metaUnoriginal: {
    label: "Straight Arrow News: Meta's July 2025 crackdown on unoriginal Facebook content",
    url: "https://san.com/cc/meta-targets-spam-removes-10-million-facebook-impersonator-profiles/",
  },
  ytInauthentic: {
    label: "Search Engine Journal: YouTube's July 2025 'inauthentic content' monetization update",
    url: "https://www.searchenginejournal.com/youtube-targets-mass-produced-content-in-monetization-update/550337/",
  },
  carryBI: {
    label: "Business Insider India: CarryMinati's YouTube vs TikTok video removed (May 2020)",
    url: "https://www.businessinsider.in/entertainment/news/carry-minati-youtube-vs-tiktok-video-removed-for-violating-terms-of-service/articleshow/75749665.cms",
  },
  carryQuint: {
    label: "The Quint: why the roast video drew mass reports",
    url: "https://www.thequint.com/neon/gender/carryminati-tik-tok-vs-youtube-roast-video-removed-homophobia",
  },
  memePurge: {
    label: "Tubefilter: Instagram permanently suspends roughly 30 meme accounts (July 2019)",
    url: "https://tubefilter.com/2019/07/31/instagram-purges-meme-accounts-millions-followers/",
  },
  baapOfChart: {
    label: "The Week: SEBI orders finfluencer 'Baap of Chart' to refund Rs 17 crore (Dec 2024)",
    url: "https://www.theweek.in/news/biz-tech/2024/12/03/why-sebi-ordered-finfluencer-baap-of-charts-to-refund-rs-17-crore-collected-from-investors.html",
  },
  enderman: {
    label: "Dexerto: tech YouTuber's 350K-subscriber channel terminated by automated systems (Nov 2025)",
    url: "https://www.dexerto.com/youtube/tech-youtuber-irate-as-ai-wrongfully-terminates-account-with-350k-subscribers-3278848/",
  },
};

export const SOURCE_ORDER = Object.keys(SOURCES) as SourceId[];

export const STATS: { value: string; label: string; source: SourceId }[] = [
  {
    value: "2.5B",
    label: "Content ID copyright claims on YouTube in 2025. Over 99% of copyright actions are automated.",
    source: "contentId2025",
  },
  {
    value: "3 strikes",
    label: "in 90 days and a YouTube channel is subject to termination, with every video on it.",
    source: "strikes",
  },
  {
    value: "98%",
    label: "of the 1,015 influencer ads ASCI investigated in 2024-25 had to be modified.",
    source: "ascify25",
  },
  {
    value: "₹50 lakh",
    label: "maximum CCPA penalty for repeat misleading endorsements, plus a ban on endorsing of up to 3 years.",
    source: "ccpa",
  },
];

export const SHIFTS: { title: string; body: string; sources: SourceId[] }[] = [
  {
    title: "Enforcement is automated",
    body: "Content ID matched 2.5 billion claims last year. Automated systems match pixels and audio; they do not read your intent, your licence email or your fair-use argument.",
    sources: ["contentId2025"],
  },
  {
    title: "Reposting now costs money",
    body: "In July 2025 YouTube renamed 'repetitious' content to 'inauthentic' and stepped up enforcement, and Meta began suspending Facebook monetization for accounts that repeatedly repost others' videos.",
    sources: ["ytInauthentic", "metaUnoriginal"],
  },
  {
    title: "Regulators fine creators, not just brands",
    body: "India's consumer protection authority can fine endorsers up to ₹10 lakh for a first misleading endorsement and ₹50 lakh for repeats, and bar them from endorsing.",
    sources: ["ccpa"],
  },
  {
    title: "Strikes compound",
    body: "Three copyright strikes inside 90 days puts the whole channel up for termination. Deleting the video afterwards does not remove the strike.",
    sources: ["strikes"],
  },
];

export type CaseStudy = {
  outcome: string;
  who: string;
  when: string;
  title: string;
  happened: string;
  flagged: string[];
  // Heading over `flagged`; defaults to "What CreatorShield checks for".
  flaggedTitle?: string;
  limits: string;
  sources: SourceId[];
};

export const CASES: CaseStudy[] = [
  {
    outcome: "Video removed",
    who: "CarryMinati",
    when: "May 2020",
    title: "India's most-liked video, gone in a week",
    happened:
      "The 'YouTube vs TikTok: The End' roast became the most-liked YouTube video in India within days, with over 6.7 million likes. YouTube removed it after mass reports; coverage tied the removal to the harassment and cyberbullying policy and to slurs in the video.",
    flagged: [
      "Slurs and targeted insults in the transcript, each pinned to its timestamp",
      "Cited YouTube's harassment and hate speech policies, with the clause it matched",
      "Suggested cuts and rewordings that keep the joke without the slur",
    ],
    limits:
      "Satire and roasts get a context review, not an automatic pass or fail. A human still decides where the line is.",
    sources: ["carryBI", "carryQuint"],
  },
  {
    outcome: "Accounts permanently disabled",
    who: "~30 Instagram meme pages",
    when: "July 2019",
    title: "30 million followers deleted overnight",
    happened:
      "Instagram permanently disabled about 30 meme accounts with over 30 million followers between them, including pages with 13 million and 8 million followers. Instagram cited multiple policy violations; much of the coverage pointed to pages built on reposting other people's content.",
    flagged: [
      "Other accounts' @handles and watermarks visible in frames",
      "The same footage already in your catalogue, including mirrored copies",
      "A rights-ledger entry for every permission, so credited reposts are on record",
    ],
    limits:
      "Account-level issues such as buying or selling accounts are outside a content review. We check what you post, not how the account is run.",
    sources: ["memePurge"],
  },
  {
    outcome: "Barred by regulator",
    who: "'Baap of Chart' (finfluencer)",
    when: "Oct 2023 – Dec 2024",
    title: "A ₹17.2 crore refund order",
    happened:
      "SEBI found that stock tips were given 'under the guise' of educational courses, with assured returns used to sell them. Its final order barred the finfluencer from the securities market for a year and ordered ₹17.2 crore refunded.",
    flagged: [
      "'Guaranteed returns' and similar claims in speech, captions and on-screen text",
      "ASCI's rule that technical financial advice needs a disclosed qualification, such as SEBI registration",
      "Missing disclosure of the paid course behind the content",
    ],
    limits:
      "We review the content. Whether a business needs a SEBI registration is a legal question for a professional.",
    sources: ["baapOfChart"],
  },
  {
    outcome: "Channel terminated, then reinstated",
    who: "Enderman (tech, 350K subscribers)",
    when: "November 2025",
    title: "Not every ban is your fault",
    happened:
      "YouTube's systems linked the channel to an unrelated channel with three copyright strikes and terminated it. It was reinstated about a day later, after a public outcry.",
    flaggedTitle: "What would have helped",
    flagged: [
      "An evidence pack ready to attach to the appeal: original-file fingerprints, licences and proof",
      "A rights ledger showing which channels you own and what you're licensed to use",
    ],
    limits:
      "Prevent it. No pre-publication tool can stop a platform's own mistake, and anyone promising a 'ban-proof' channel is selling something no one can deliver.",
    sources: ["enderman"],
  },
];

export const SCENARIOS: { who: string; risk: string; fix: string }[] = [
  {
    who: "Fitness creator, 400K followers",
    risk: "Paid shake deal, with #ad as the 14th hashtag at the end of the caption. ASCI says disclosure buried among hashtags does not count.",
    fix: "Flagged high: 'Paid agreement with FitFuel: opening disclosure needs review'. Fix: start the caption with 'Ad:'.",
  },
  {
    who: "Agency managing 12 creators",
    risk: "The same stock transition clip went out on two clients' channels in one week, one of them unlicensed.",
    fix: "The catalogue match shows 'footage also appears under Client B' with both timestamps, before the second post.",
  },
  {
    who: "Cricket edits page, 1M followers",
    risk: "Highlights with a broadcaster's scorebug visible from 0:12 to 0:41.",
    fix: "Flagged as third-party broadcast footage. Either record the licence in the ledger or cut that segment.",
  },
];

export const FAQ: { q: string; a: string }[] = [
  {
    q: "Can you guarantee my channel won't be struck or banned?",
    a: "No, and nobody honestly can. Platforms decide, their systems make mistakes, and rights-holders can claim content at any time. We catch the problems we can see before you post, show the evidence and cite the official rule, so you decide with your eyes open.",
  },
  {
    q: "Does this replace YouTube's own Checks?",
    a: "No. Use both. YouTube's checks look for Content ID matches and ad suitability after you upload. CreatorShield runs before you upload, on Instagram as well as YouTube, and also covers community guidelines, sponsorship disclosure, claims and your own licences.",
  },
  {
    q: "Where do the policy citations come from?",
    a: "From a versioned library of 35 rules, each written from an official YouTube, Instagram, Meta or ASCI page that was read and dated. The AI can only cite rules in that library; anything else is thrown away.",
  },
  {
    q: "Do you scrape or download my posts?",
    a: "No. You upload a file, or connect your own account through the official Instagram and YouTube APIs. YouTube does not allow its videos to be downloaded, so for YouTube you attach your own copy.",
  },
  {
    q: "What happens to my video?",
    a: "It is deleted automatically after 72 hours by default, and you can delete it any time. Large files are turned into a 1080p working copy with location metadata stripped. Only a fingerprint is kept for repost matching, and you control how long.",
  },
  {
    q: "Does it work in Hindi?",
    a: "Yes. Speech, captions and on-screen text in Hindi and English, with evidence quoted in the original script.",
  },
];
