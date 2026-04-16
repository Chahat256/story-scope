from groq import Groq
import json
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone

from app.core.config import settings
from app.models.schemas import (
    AnalysisReport, NovelOverview, CharacterAnalysis, RelationshipAnalysis,
    ThemeAnalysis, TropeAnalysis, SupportingPassage, RelationshipType
)
from app.services.embedding_service import retrieve_chunks

logger = logging.getLogger(__name__)

client = Groq(api_key=settings.groq_api_key)


def parse_json_response(content: str) -> any:
    """Parse JSON from LLM response, stripping markdown fences and recovering truncated arrays."""
    if not content or not content.strip():
        raise ValueError("Empty response from LLM")
    text = content.strip()
    # Strip ```json ... ``` or ``` ... ``` fences
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if "```" in text:
            text = text.rsplit("```", 1)[0]
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Attempt recovery: extract the outermost [...] or {...} and re-parse
        for start_char, end_char in [("[", "]"), ("{", "}")]:
            start = text.find(start_char)
            end = text.rfind(end_char)
            if start != -1 and end > start:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    pass
        raise


def llm_call_with_retry(prompt: str, model: str, max_tokens: int, max_attempts: int = 3) -> any:
    """Call the LLM and parse JSON, retrying on malformed responses."""
    last_error: Exception = ValueError("No attempts made")
    for attempt in range(1, max_attempts + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return parse_json_response(response.choices[0].message.content)
        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            logger.warning(f"JSON parse failed on attempt {attempt}/{max_attempts}: {e}")
    raise ValueError(f"LLM returned invalid JSON after {max_attempts} attempts: {last_error}")

# Predefined trope library
TROPE_LIBRARY = [
    # ── Classic / literary tropes ────────────────────────────────────────────
    {"id": "chosen_one", "name": "The Chosen One", "description": "A character destined or selected to fulfill a special purpose"},
    {"id": "redemption_arc", "name": "Redemption Arc", "description": "A character moving from wrongdoing or failure toward moral recovery"},
    {"id": "reluctant_hero", "name": "Reluctant Hero", "description": "A protagonist who doesn't want the heroic role thrust upon them"},
    {"id": "coming_of_age", "name": "Coming of Age", "description": "A protagonist's journey from youth to maturity, often through trials"},
    {"id": "forbidden_love", "name": "Forbidden Love", "description": "A romantic relationship opposed by society, family, or circumstance"},
    {"id": "mentor_student", "name": "Mentor and Student", "description": "A wise guide shapes a younger, less experienced protagonist"},
    {"id": "fish_out_of_water", "name": "Fish Out of Water", "description": "A character placed in an environment completely foreign to them"},
    {"id": "dark_secret", "name": "Dark Secret", "description": "A hidden truth that, if revealed, would change everything"},
    {"id": "found_family", "name": "Found Family", "description": "Characters forming deep familial bonds outside biological family"},
    {"id": "rival_turned_ally", "name": "Rival Turned Ally", "description": "An adversary who becomes a companion through shared experience"},
    {"id": "tragic_villain", "name": "Tragic Villain", "description": "An antagonist whose evil is rooted in understandable pain or loss"},
    {"id": "love_triangle", "name": "Love Triangle", "description": "A protagonist torn between two romantic interests"},
    {"id": "power_corrupts", "name": "Power Corrupts", "description": "A character's acquisition of power leads to their moral downfall"},
    {"id": "quest_narrative", "name": "Quest Narrative", "description": "Characters pursuing a specific goal through a series of trials"},
    {"id": "dystopia", "name": "Dystopian Society", "description": "A story set in an oppressive, controlled, or degraded society"},
    {"id": "revenge_plot", "name": "Revenge Plot", "description": "A protagonist driven by desire for vengeance"},
    {"id": "identity_discovery", "name": "Identity Discovery", "description": "A character uncovering the truth about who they really are"},
    {"id": "sacrifice", "name": "Heroic Sacrifice", "description": "A character gives up something precious (including their life) for others"},
    {"id": "unreliable_narrator", "name": "Unreliable Narrator", "description": "The story's narrator whose credibility is compromised"},
    {"id": "social_class_conflict", "name": "Class Conflict", "description": "Tension between characters of different social or economic strata"},
    {"id": "man_vs_nature", "name": "Man vs. Nature", "description": "Characters in conflict with the natural world"},
    {"id": "prophecy", "name": "Prophecy", "description": "A foretold future event that drives character actions"},
    {"id": "secret_identity", "name": "Secret Identity", "description": "A character concealing who they truly are"},
    {"id": "unlikely_allies", "name": "Unlikely Allies", "description": "Characters from opposing worlds or beliefs joining forces"},
    {"id": "obsession", "name": "Obsession", "description": "A character consumed by a singular fixation to destructive ends"},
    # ── Love triangles and multi-person dynamics ──────────────────────────────
    {"id": "sibling_triangle", "name": "Sibling Triangle", "description": "A love triangle in which two of the three participants are siblings"},
    {"id": "best_friend_triangle", "name": "Best Friend Triangle", "description": "A love triangle involving a protagonist and their best friend as rivals for the same person"},
    {"id": "bf_gf_best_friend", "name": "Boyfriend/Girlfriend's Best Friend", "description": "Romantic tension developing between a character and their partner's best friend"},
    {"id": "tug_of_war_triangle", "name": "Tug-of-war Triangle", "description": "Two love interests who openly and actively compete for a protagonist's affection"},
    {"id": "vampire_werewolf_triangle", "name": "Vampire-Werewolf Triangle", "description": "A supernatural love triangle between a human, a vampire, and a werewolf"},
    {"id": "betty_and_veronica_triangle", "name": "Betty & Veronica Triangle", "description": "A protagonist choosing between a safe familiar love and an exciting dangerous one"},
    {"id": "two_person_love_triangle", "name": "Two-Person Love Triangle", "description": "Mistaken identity creates the illusion of a love triangle with only two people involved"},
    # ── Pregnancy, children, and family complications ─────────────────────────
    {"id": "accidental_pregnancy", "name": "Accidental Pregnancy", "description": "An unplanned pregnancy forces a relationship to evolve in unexpected directions"},
    {"id": "secret_lovechild", "name": "Secret Lovechild", "description": "A hidden child from a past relationship is dramatically revealed years later"},
    {"id": "secret_baby", "name": "Secret Baby", "description": "One parent conceals a child's existence from the other until the truth is revealed"},
    {"id": "unexpected_baby", "name": "Unexpected Baby", "description": "An unplanned child forces two people to navigate parenthood and discover love together"},
    # ── Marriage and commitment tropes ────────────────────────────────────────
    {"id": "arranged_marriage", "name": "Arranged Marriage", "description": "Partners brought together by family or social obligation rather than romantic choice"},
    {"id": "childhood_marriage_pact", "name": "Childhood Marriage Pact", "description": "Two people made a childhood promise to marry each other that resurfaces in adulthood"},
    {"id": "wartime_wedding", "name": "Wartime Wedding", "description": "A hasty marriage undertaken during conflict or crisis before one partner ships out"},
    {"id": "jilted_bride", "name": "Jilted Bride", "description": "A character left at the altar who must rebuild their life and find unexpected new love"},
    {"id": "runaway_fiance", "name": "Runaway Fiancé", "description": "A character who flees their impending wedding and encounters romance on the run"},
    {"id": "marriage_pact", "name": "Marriage Pact", "description": "Two friends agree to marry each other if still single by a certain age"},
    {"id": "marriage_before_romance", "name": "Marriage Before Romance", "description": "Characters who marry for practical reasons before falling genuinely in love"},
    {"id": "vegas_drunk_marriage", "name": "Vegas/Drunk Marriage", "description": "An impulsive marriage made under the influence that leads to real and lasting love"},
    {"id": "altar_diplomacy", "name": "Altar Diplomacy", "description": "A marriage arranged for political, dynastic, or strategic reasons"},
    {"id": "honorable_marriage", "name": "Honorable Marriage", "description": "Marriage undertaken for reasons of honor or duty before romantic love develops"},
    {"id": "in_love_with_wedding_party", "name": "In Love with the Wedding Party", "description": "Falling for a best man, bridesmaid, or other wedding party member during the celebrations"},
    {"id": "double_in_law_marriage", "name": "Double In-Law Marriage", "description": "Two sets of siblings each marry into the other's family, creating a double bond"},
    # ── Fake, secret, and unconventional relationship dynamics ────────────────
    {"id": "fake_relationship", "name": "Fake Relationship", "description": "Characters pretend to be in a relationship for social purposes and develop genuine feelings"},
    {"id": "secret_relationship", "name": "Secret Relationship", "description": "A couple who must hide their romance from the world around them"},
    {"id": "prank_date", "name": "Prank Date", "description": "A date that begins as a joke or bet develops into genuine unexpected romance"},
    {"id": "the_bet", "name": "The Bet", "description": "Characters make a wager involving romantic conquest, only to develop real feelings"},
    {"id": "blackmail_date", "name": "Blackmail Date", "description": "One character coerces another into a relationship using leverage or secrets"},
    {"id": "revenge_romance", "name": "Revenge Romance", "description": "A character pursues romance as part of a revenge scheme but falls genuinely in love"},
    # ── One-night stands, hookups, and physical-first relationships ───────────
    {"id": "one_night_stand", "name": "One Night Stand", "description": "A single night of passion that unexpectedly grows into something lasting"},
    {"id": "no_feelings_hookup", "name": "The No Feelings Hookup", "description": "Characters who agree to a purely physical arrangement but inevitably develop emotions"},
    {"id": "friends_with_benefits", "name": "Friends with Benefits", "description": "Friends who add a physical dimension to their relationship with romantic complications"},
    # ── Multi-partner and non-traditional romance ─────────────────────────────
    {"id": "polyamory", "name": "Polyamory", "description": "A romance involving consensual multi-partner relationships with full knowledge of all involved"},
    {"id": "mmf", "name": "MMF", "description": "A romance or relationship dynamic between two men and one woman"},
    {"id": "mfm", "name": "MFM", "description": "Two men who both pursue or share a romantic relationship with one woman"},
    {"id": "mm", "name": "MM Romance", "description": "A romance between two men"},
    {"id": "mff", "name": "MFF", "description": "A romance or relationship dynamic between one man and two women"},
    {"id": "harem_of_friends", "name": "Harem of Friends", "description": "A protagonist surrounded by multiple devoted companions, each a potential love interest"},
    {"id": "band_of_brothers", "name": "Band of Brothers", "description": "A tight-knit group of men bonded by shared hardship, with romantic subplots woven through"},
    # ── Enemies, rivals, and hate-to-love ────────────────────────────────────
    {"id": "enemies_to_lovers", "name": "Enemies to Lovers", "description": "Characters who begin as genuine antagonists and gradually, reluctantly fall in love"},
    {"id": "hate_to_love", "name": "Hate to Love You", "description": "Characters who start in mutual animosity and discover love beneath the hostility"},
    {"id": "old_enemies", "name": "Old Enemies", "description": "Former rivals from school, work, or life who are forced together and fall in love"},
    {"id": "rivals", "name": "Rivals", "description": "Direct competitors in the same field whose rivalry masks and fuels mutual attraction"},
    {"id": "love_hate", "name": "Love/Hate", "description": "A relationship that oscillates passionately between fierce conflict and fierce romance"},
    {"id": "nobody_thinks_it_will_work", "name": "Nobody Thinks It Will Work", "description": "A couple who must prove skeptical friends and family wrong about their relationship"},
    {"id": "bully_romance", "name": "Bully Romance", "description": "A former bully and their target develop complicated, charged romantic feelings"},
    {"id": "bully_turned_nice_guy", "name": "Bully Turned Nice Guy", "description": "A former antagonist who reforms and seeks genuine redemption through love"},
    # ── Friends-to-lovers and reunion romance ─────────────────────────────────
    {"id": "friends_to_lovers", "name": "Friends to Lovers", "description": "A deep, established friendship that slowly and naturally evolves into romantic love"},
    {"id": "childhood_friends_reunion", "name": "Childhood Friends Reunion", "description": "Former childhood friends who reconnect as adults and discover unexpected romantic feelings"},
    {"id": "high_school_sweethearts", "name": "High School Sweethearts", "description": "Former teenage lovers whose story continues or is told in retrospect as adults"},
    {"id": "second_chance_romance", "name": "Second Chance Romance", "description": "Former lovers who reunite and get another chance at the relationship that once failed"},
    {"id": "new_old_flame", "name": "New Old Flame", "description": "A character encounters a past love interest in an entirely new and unexpected context"},
    {"id": "return_to_hometown", "name": "Return to Hometown", "description": "A character returning home encounters a past love or discovers an unexpected new one"},
    {"id": "the_one_that_got_away", "name": "The One That Got Away", "description": "A character pursues reconciliation with a former love they have never stopped thinking about"},
    {"id": "all_grown_up", "name": "All Grown Up", "description": "A character encounters someone from their past who has transformed dramatically with time"},
    {"id": "working_with_ex", "name": "Working with the Ex", "description": "Former romantic partners who are forced to collaborate professionally with lingering feelings"},
    # ── Correspondence and long-distance ─────────────────────────────────────
    {"id": "pen_pals", "name": "Pen Pals", "description": "Regular correspondents who develop romantic feelings before or despite meeting in person"},
    {"id": "penpal_enemy", "name": "Penpal Enemy", "description": "Correspondents who are antagonists in person but fall for each other through their letters"},
    {"id": "long_distance", "name": "Long Distance Relationship", "description": "Lovers separated by geography who fight to maintain and grow their relationship"},
    # ── Forbidden and taboo romance ───────────────────────────────────────────
    {"id": "sleeping_with_teacher", "name": "Sleeping with the Teacher", "description": "A forbidden romance between a student and an instructor"},
    {"id": "sleeping_with_boss", "name": "Sleeping with the Boss", "description": "A romance between an employee and their professional superior"},
    {"id": "step_sibling_crush", "name": "Step-sibling Crush", "description": "Romantic tension developing between step-siblings with no blood relation"},
    {"id": "step_siblings", "name": "Step-siblings", "description": "Step-siblings navigating complicated romantic feelings within a blended family"},
    {"id": "teacher_parent_relationship", "name": "Teacher/Parent Relationship", "description": "A romance between a teacher and the parent of one of their students"},
    {"id": "pining_after_parent", "name": "Pining After His Parent", "description": "Romantic feelings developed for a parent's romantic partner or close friend"},
    {"id": "forbidden_priest", "name": "Priest/Clergy Romance", "description": "Forbidden romance involving a religious figure bound by vows of celibacy"},
    {"id": "siblings_ex", "name": "Sibling's Ex", "description": "Falling for a sibling's former romantic partner, violating an unspoken rule"},
    {"id": "best_friends_sibling", "name": "Best Friend's Sibling", "description": "Falling in love with a best friend's brother or sister, risking the friendship"},
    {"id": "best_friends_ex", "name": "Best Friend's Ex", "description": "Pursuing romance with a friend's former partner despite the complications"},
    {"id": "best_friends_lover", "name": "Best Friend's Lover", "description": "Developing feelings for someone already in a relationship with your best friend"},
    # ── Professional and workplace romance ────────────────────────────────────
    {"id": "office_romance_coworkers", "name": "Office Romance: Coworkers", "description": "Colleagues who develop romantic feelings while working together"},
    {"id": "office_romance_rivals", "name": "Office Romance: Rivals", "description": "Competing coworkers or business rivals who fall in love"},
    {"id": "doctor_patient", "name": "The Doctor and Patient", "description": "A romance that develops between a medical professional and their patient"},
    {"id": "lawyer_client", "name": "The Lawyer and Client", "description": "A romance that develops between a legal professional and their client"},
    # ── Age gap romance ───────────────────────────────────────────────────────
    {"id": "age_gap_older_hero", "name": "Age Gap: Older Hero", "description": "A romance featuring a significantly older male partner and younger heroine"},
    {"id": "age_gap_younger_hero", "name": "Age Gap: Younger Hero", "description": "A romance featuring a significantly younger male partner and older heroine"},
    # ── Wealthy, powerful, and celebrity heroes ───────────────────────────────
    {"id": "billionaire_playboy", "name": "Billionaire Playboy", "description": "A fabulously wealthy, experienced man who unexpectedly falls for an ordinary woman"},
    {"id": "mafia_organized_crime", "name": "Mafia / Organized Crime", "description": "A romance set within the dangerous, glamorous world of organized crime"},
    {"id": "celebrity_hero", "name": "Celebrity Hero", "description": "A famous person — actor, athlete, musician — who falls for an ordinary person"},
    {"id": "rockstar_romance", "name": "Rockstar Romance", "description": "A romance involving a musician or rock star and the chaos of their world"},
    {"id": "royalty_falls_for_commoner", "name": "Royalty Falls for Commoner", "description": "A royal character who falls in love with someone of common birth"},
    {"id": "movie_star_commoner", "name": "Movie Star Falls for Commoner", "description": "A film celebrity who falls for someone living an ordinary life"},
    {"id": "politician_romance", "name": "Politician Romance", "description": "Romance involving a political figure and the complications of public life"},
    {"id": "secret_royal_billionaire", "name": "Secret Royal/Billionaire", "description": "A character's true status as royalty or the ultra-wealthy is concealed, then revealed"},
    # ── Domestic, hired help, and proximity romance ────────────────────────────
    {"id": "the_nanny", "name": "The Nanny", "description": "A romance that develops between an employer and their child's caretaker"},
    {"id": "the_maid", "name": "The Maid", "description": "A romance that develops between an employer and their domestic worker"},
    {"id": "the_bodyguard", "name": "The Bodyguard", "description": "A romance between a person and their professional protector"},
    {"id": "the_pool_boy", "name": "The Pool Boy", "description": "A romance between an employer and a hired worker in close domestic proximity"},
    {"id": "the_landscaper", "name": "The Landscaper", "description": "Romance sparked through recurring contact with a hired outdoor worker"},
    {"id": "guardian", "name": "Guardian", "description": "Romantic tension developing between a ward and their legal guardian"},
    {"id": "parent_child_carer", "name": "Parent's Child's Carer", "description": "Romance between a single parent and their child's teacher, nanny, or carer"},
    # ── Opposites attract and personality contrasts ───────────────────────────
    {"id": "grumpy_sunshine", "name": "Grumpy/Sunshine", "description": "A brooding, pessimistic character who falls for an optimistic, relentlessly cheerful one"},
    {"id": "bad_boy_good_girl", "name": "Bad Boy / Good Girl", "description": "A rebellious, rule-breaking character who falls for a wholesome, virtuous one"},
    {"id": "playboy_virgin", "name": "Playboy / Virgin", "description": "An experienced, worldly romantic pursues an innocent and inexperienced love interest"},
    {"id": "opposites_attract", "name": "Opposites Attract", "description": "Characters with fundamentally different personalities, values, or lifestyles who fall in love"},
    {"id": "physically_mismatched", "name": "Physically Mismatched", "description": "A romance between characters with strikingly different physical appearances or builds"},
    {"id": "want_different_things", "name": "Want Different Things", "description": "A couple deeply in love whose life goals or visions for the future seem incompatible"},
    # ── Sports romance ────────────────────────────────────────────────────────
    {"id": "sports_romance_football", "name": "Sports Romance: Football/Rugby", "description": "Romance set in the world of football or rugby, often featuring an athlete hero"},
    {"id": "sports_romance_baseball", "name": "Sports Romance: Baseball", "description": "Romance set in the world of baseball"},
    {"id": "sports_romance_hockey", "name": "Sports Romance: Hockey", "description": "Romance set in the world of hockey, often featuring intense, physical heroes"},
    {"id": "sports_romance_basketball", "name": "Sports Romance: Basketball", "description": "Romance set in the world of basketball"},
    {"id": "sports_romance_soccer", "name": "Sports Romance: Soccer", "description": "Romance set in the world of soccer"},
    {"id": "sports_romance_tennis", "name": "Sports Romance: Tennis", "description": "Romance involving a tennis instructor or player"},
    {"id": "sports_romance_lacrosse", "name": "Sports Romance: Lacrosse", "description": "Romance set in the world of lacrosse"},
    {"id": "sports_romance_wrestling", "name": "Sports Romance: Wrestling", "description": "Romance set in the world of wrestling"},
    {"id": "jock_nerdy_tutor", "name": "Jock Falls for Nerdy Tutor", "description": "A popular athlete develops genuine feelings for an academic tutor"},
    # ── Captivity, rescue, and danger ────────────────────────────────────────
    {"id": "captive_falls_for_captor", "name": "Captive Falls for Captor", "description": "A prisoner or hostage who develops romantic feelings for their captor"},
    {"id": "rescue_romance", "name": "Rescue Romance", "description": "One character saves another from danger, sparking a powerful romantic connection"},
    {"id": "kidnapped", "name": "Kidnapped", "description": "A character is abducted, and romance complicates the captivity situation"},
    {"id": "damsel_in_distress", "name": "Damsel/Dude in Distress", "description": "A character repeatedly rescued by their love interest from peril"},
    {"id": "the_bodyguard_dynamic", "name": "Protector", "description": "A character assigned to protect another who develops deep romantic feelings for them"},
    {"id": "if_i_cant_have_you", "name": "If I Can't Have You, Nobody Will", "description": "An obsessive love interest who cannot accept rejection and becomes dangerous"},
    # ── Setting-based and circumstantial romance ──────────────────────────────
    {"id": "road_trip_romance", "name": "Road Trip Romance", "description": "Love sparked or deepened during a shared journey across distance"},
    {"id": "romance_on_set", "name": "Romance on Set", "description": "Actors or crew members who fall in love during the filming of a production"},
    {"id": "cooking_show_romance", "name": "Cooking Show Romance", "description": "Romance sparked during a culinary competition or food-oriented setting"},
    {"id": "reality_tv_romance", "name": "Reality TV Show", "description": "Romance emerging from the pressure-cooker environment of reality television"},
    {"id": "trapped_in_elevator", "name": "Trapped in an Elevator", "description": "Forced proximity in a confined space that strips away pretense and sparks romance"},
    {"id": "stranded", "name": "Stranded", "description": "Characters isolated together in a remote location who develop romantic feelings"},
    {"id": "scavenger_hunt_bonding", "name": "Scavenger Hunt Bonding", "description": "A shared competition or game that leads to unexpected romantic connection"},
    {"id": "military_romance", "name": "Military Romance", "description": "A romance set against the backdrop of military service, deployment, or conflict"},
    {"id": "men_in_uniform", "name": "Men in Uniform", "description": "Romance with military personnel, police officers, or other uniformed service members"},
    # ── First meetings and coincidence ────────────────────────────────────────
    {"id": "love_at_first_sight", "name": "Love at First Sight", "description": "Characters who experience instant, overwhelming romantic attraction upon meeting"},
    {"id": "blind_date_mixup", "name": "Blind Date Mixup", "description": "A mistaken identity or mix-up during a blind date leads to unexpected romance"},
    {"id": "love_letter_lunacy", "name": "Love Letter Lunacy", "description": "Romantic letters sent to the wrong person that spark unexpected feelings"},
    {"id": "mistaken_identity", "name": "Mistaken Identity", "description": "A character mistaken for someone else becomes entangled in an unintended romance"},
    {"id": "mistaken_declaration", "name": "Mistaken Declaration of Love", "description": "A declaration meant for another person leads unexpectedly to real romance"},
    {"id": "matchmaker_crush", "name": "Matchmaker Crush", "description": "A matchmaker who falls for one of the people they are trying to set up"},
    {"id": "matchmaker_gone_wrong", "name": "Matchmaker Gone Wrong", "description": "A matchmaking scheme backfires spectacularly in unexpected romantic ways"},
    {"id": "relationship_coach", "name": "Relationship Coach", "description": "A relationship advisor who develops genuine feelings for a client"},
    # ── Proximity and cohabitation ────────────────────────────────────────────
    {"id": "roommate_romance", "name": "Roommate Romance", "description": "Housemates who share space and gradually fall in love"},
    {"id": "innocent_cohabitation", "name": "Innocent Cohabitation", "description": "Two characters who live together platonically and slowly develop romantic feelings"},
    {"id": "loving_thy_neighbor", "name": "Loving Thy Neighbor", "description": "A romance that develops between neighbors in close proximity"},
    # ── Hidden truths and reveals ─────────────────────────────────────────────
    {"id": "disguise", "name": "Disguise", "description": "A character conceals their true appearance or identity in a romantic context"},
    {"id": "undercover_love", "name": "Undercover Love", "description": "A character working undercover on an assignment develops genuine romantic feelings"},
    {"id": "secret_heir", "name": "Secret/Lost Heir", "description": "A character discovers they are heir to a significant legacy, complicating their romance"},
    {"id": "secret_admirer", "name": "Secret Admirer", "description": "Anonymous expressions of love that gradually reveal a surprising or familiar identity"},
    {"id": "everyone_can_see_it", "name": "Everyone Can See It", "description": "The romantic tension between two people is obvious to everyone around them but the pair"},
    {"id": "oblivious_to_love", "name": "Oblivious to Love", "description": "A character who is entirely unaware of another's deep romantic feelings for them"},
    {"id": "last_to_know", "name": "Last to Know", "description": "The protagonist is the final person to realize their own or another's romantic feelings"},
    # ── Emotional and psychological barriers ──────────────────────────────────
    {"id": "sworn_off_relationship", "name": "Sworn Off Relationships", "description": "A character who has vowed to avoid romance is swept irresistibly off their feet"},
    {"id": "afraid_to_commit", "name": "Afraid to Commit", "description": "A character who resists formal romantic commitment despite obvious genuine feelings"},
    {"id": "cant_say_i_love_you", "name": "Can't Say I Love You", "description": "Characters who deeply struggle to verbalize their romantic feelings to each other"},
    {"id": "lovers_in_denial", "name": "Lovers in Denial", "description": "Characters who refuse to acknowledge their obvious mutual romantic feelings"},
    {"id": "not_good_enough", "name": "Not Good Enough", "description": "A character who believes they are fundamentally unworthy of their love interest"},
    {"id": "break_up_to_save", "name": "Break Up to Save Him/Her", "description": "A character ends the relationship to protect their partner from danger or pain"},
    {"id": "emotional_scars", "name": "Emotional Scars", "description": "Characters whose past trauma profoundly shapes their capacity and fear of love"},
    {"id": "rejected_as_unworthy", "name": "Rejected as Unworthy", "description": "A character deemed unsuitable by the family, friends, or social circle of their love interest"},
    # ── Character archetypes ──────────────────────────────────────────────────
    {"id": "tortured_hero", "name": "Tortured Hero", "description": "A protagonist burdened by trauma, guilt, or profound inner darkness"},
    {"id": "alpha_hero", "name": "Alpha Hero / Antihero", "description": "A dominant, morally complex hero who is irresistible despite — or because of — his flaws"},
    {"id": "loveable_rogue", "name": "Loveable Rogue", "description": "A charming, morally grey character who wins deep affection despite obvious flaws"},
    {"id": "wallflower", "name": "Wallflower", "description": "A shy, overlooked character who is truly seen and loved by exactly the right person"},
    {"id": "ladykiller_in_love", "name": "Ladykiller in Love", "description": "A notorious playboy or seducer who falls genuinely and helplessly in love for the first time"},
    {"id": "sleeps_with_everyone_but_you", "name": "Sleeps with Everyone but You", "description": "A known playboy or playgirl who makes a conspicuous and deliberate exception for one person"},
    {"id": "ugly_duckling", "name": "The Ugly Duckling", "description": "A character undergoes a transformation that dramatically changes how others perceive and treat them"},
    {"id": "too_dumb_to_live", "name": "Too Dumb to Live", "description": "A protagonist whose naïve decisions repeatedly endanger them, drawing in protective love interests"},
    # ── Loss, grief, and new beginnings ──────────────────────────────────────
    {"id": "widow_widower", "name": "Widow/Widower", "description": "A bereaved character who finds unexpected new love after profound loss"},
    {"id": "orphan_bonding", "name": "Orphan Bonding", "description": "Characters who bond deeply over shared experiences of loss, abandonment, or chosen family"},
    {"id": "orphan", "name": "Orphan", "description": "A character without parents who finds love, belonging, and a new family"},
    {"id": "love_interest_reminds_family", "name": "Love Interest Reminds of Family", "description": "Attraction complicated by a love interest's resemblance to a lost or estranged family member"},
    {"id": "injury_recovery", "name": "Injury/Illness Recovery", "description": "A romance that deepens through one character tenderly caring for an injured or ill other"},
    # ── Fairy tale, fantasy, and genre romance ────────────────────────────────
    {"id": "cinderella_circumstance", "name": "Cinderella Circumstance", "description": "A character of humble origins who is elevated through love and circumstance"},
    {"id": "beauty_and_the_beast", "name": "Beauty and the Beast", "description": "A beautiful character who falls for someone initially perceived as monstrous or frightening"},
    {"id": "fairytale_retelling", "name": "Fairytale Retelling", "description": "A romantic story retelling or inspired by a classic fairy tale with contemporary twists"},
    {"id": "time_travel", "name": "Time Travel", "description": "A romance that spans or is complicated by travel across different time periods"},
    {"id": "love_potion", "name": "Love Potion", "description": "A magical or chemical substance causes or fatally complicates romantic feelings"},
    {"id": "soulmates_destined", "name": "Destined to Be Together", "description": "Characters believed by fate, prophecy, or the universe itself to be meant for each other"},
    {"id": "courtly_love", "name": "Courtly Love", "description": "An idealized, often chaste, and sometimes unconsummated romantic devotion from afar"},
    # ── Social and economic romance ───────────────────────────────────────────
    {"id": "rich_and_poor", "name": "The Rich and the Poor", "description": "A romance that bridges extreme economic inequality between the two lovers"},
    {"id": "rags_to_riches", "name": "Rags to Riches", "description": "A character who rises from poverty to prosperity through love, talent, or circumstance"},
    {"id": "love_interest_wrong_profession", "name": "Love Interest Has the Wrong Profession", "description": "Attraction to someone whose job fundamentally conflicts with the protagonist's own values"},
    # ── Unrequited and impossible love ───────────────────────────────────────
    {"id": "unrequited_love", "name": "Unrequited Love", "description": "One-sided love that is painfully and persistently not returned"},
    {"id": "fall_for_wrong_person", "name": "Fall in Love with the Wrong Person", "description": "A character falls helplessly for someone they absolutely should not love"},
    {"id": "dating_wrong_person", "name": "Dating the Wrong Person", "description": "Pursuing a relationship with someone clearly unsuitable while unable to resist the attraction"},
    {"id": "belated_love_epiphany", "name": "Belated Love Epiphany", "description": "A character realizes — almost too late, or just in time — that they are truly in love"},
    # ── Sex industry and adult content ────────────────────────────────────────
    {"id": "sex_worker_escort", "name": "Sex Worker / Escort", "description": "A romance involving a character who works in the sex industry"},
    {"id": "sex_club", "name": "Sex Club", "description": "Romance or relationships that emerge from a secretive, erotic social environment"},
    {"id": "virgin_auction", "name": "Virgin Auction", "description": "A high-stakes scenario in which a character's first experience is sold to the highest bidder"},
    {"id": "bdsm_romance", "name": "BDSM Romance", "description": "A romance that prominently features dominance, submission, and consensual power exchange"},
    # ── Identity, passing, and changing self ──────────────────────────────────
    {"id": "changing_preferences", "name": "Changing Sexual Preferences", "description": "A character who discovers or openly acknowledges a shift in their romantic or sexual identity"},
    {"id": "amnesia", "name": "Amnesia", "description": "Memory loss that profoundly complicates, erases, or unexpectedly transforms a romantic relationship"},
    {"id": "parent_new_love", "name": "Parent's New Love", "description": "Children who must accept — or dramatically resist — a parent's new romantic partner"},
    # ── Genre and setting miscellany ─────────────────────────────────────────
    {"id": "accidental_adultery", "name": "Accidental Adultery", "description": "A character unknowingly becomes romantically involved with someone who is already taken"},
    {"id": "good_people_good_sex", "name": "Good People Have Good Sex", "description": "The convention that virtuous, emotionally healthy characters are rewarded with passionate physical intimacy"},
]


def build_sample_context(job_id: str, query: str, n: int = 12) -> str:
    """Retrieve relevant chunks and format as context string."""
    chunks = retrieve_chunks(job_id, query, top_k=n)
    if not chunks:
        return "No relevant passages found."

    parts = []
    for i, c in enumerate(chunks):
        ref = c.get("page_reference", "")
        parts.append(f"[Passage {i+1} {ref}]\n{c['text']}")

    return "\n\n---\n\n".join(parts)


def passages_from_chunks(chunks: List[Dict]) -> List[SupportingPassage]:
    return [
        SupportingPassage(
            text=c["text"][:400] + ("..." if len(c["text"]) > 400 else ""),
            page_reference=c.get("page_reference"),
            relevance=f"Relevance score: {c.get('relevance_score', 0):.2f}",
        )
        for c in chunks[:3]
    ]


def analyze_overview(job_id: str, sample_text: str) -> NovelOverview:
    """Generate a novel overview using the first portions of the text."""
    prompt = f"""You are a skilled literary analyst. Based on the following opening passages from a novel, provide a structured overview.

Text sample:
{sample_text[:6000]}

Respond with a JSON object matching exactly this structure:
{{
  "title_guess": "your best guess at the title or 'Unknown'",
  "author_guess": "your best guess at the author or null",
  "genre_guess": "e.g. 'Gothic Romance', 'Literary Fiction', 'Fantasy', etc.",
  "setting_description": "where and when the story appears to take place",
  "narrative_summary": "2-3 sentence summary of what the novel appears to be about",
  "estimated_time_period": "e.g. '19th century England' or null if unclear",
  "point_of_view": "e.g. 'First-person', 'Third-person limited', 'Omniscient'",
  "tone": "e.g. 'Dark and brooding', 'Light and comedic', 'Melancholic'"
}}

Respond only with valid JSON."""

    data = llm_call_with_retry(prompt, settings.analysis_model, max_tokens=1000)
    return NovelOverview(**data)


def analyze_characters(job_id: str) -> List[CharacterAnalysis]:
    """Identify and analyze main characters."""
    # First pass: identify names
    context = build_sample_context(job_id, "main character protagonist name introduction", n=15)

    prompt = f"""You are an expert literary analyst performing character analysis on a novel.

Relevant passages:
{context}

Task: Identify the MAIN characters (not every named person — focus on characters with significant narrative presence). For each major character, provide detailed analysis.

Respond with a JSON array. Each element must match exactly:
{{
  "name": "Character's primary name",
  "aliases": ["list", "of", "nicknames", "or", "titles"],
  "role": "protagonist | antagonist | deuteragonist | supporting",
  "defining_traits": ["trait1", "trait2", "trait3"],
  "goals": ["what this character wants or seeks"],
  "conflicts": ["internal and external conflicts this character faces"],
  "important_relationships": ["Character X - nature of relationship"],
  "supporting_passages": [
    {{
      "text": "exact short quote or paraphrase from the text supporting this analysis",
      "page_reference": "p.X if known, otherwise null",
      "relevance": "why this passage supports the character analysis"
    }}
  ],
  "confidence": "high | moderate | low"
}}

Identify between 2-6 major characters. Focus on narrative significance, not just frequency of mention.
Return only valid JSON array."""

    data = llm_call_with_retry(prompt, settings.analysis_model, max_tokens=2500)
    return [CharacterAnalysis(**c) for c in data]


def analyze_relationships(job_id: str, characters: List[CharacterAnalysis]) -> List[RelationshipAnalysis]:
    """Analyze relationships between major characters."""
    char_names = [c.name for c in characters]
    context = build_sample_context(job_id, f"relationship between {' '.join(char_names[:4])}", n=12)

    prompt = f"""You are an expert literary analyst examining character relationships in a novel.

Main characters identified: {', '.join(char_names)}

Relevant passages:
{context}

Task: Identify and analyze the KEY relationships between these characters. Focus on relationships that are narratively significant.

Valid relationship types: friendship, rivalry, romance, family, mentorship, alliance, conflict, complex

Respond with a JSON array. Each element must match:
{{
  "character_a": "Name of first character",
  "character_b": "Name of second character",
  "relationship_type": "one of the valid types above",
  "description": "1-2 sentence description of this relationship",
  "dynamics": "how the power/emotional dynamics work between them",
  "supporting_passages": [
    {{
      "text": "short quote or paraphrase from text",
      "page_reference": "p.X or null",
      "relevance": "how this passage illustrates the relationship"
    }}
  ],
  "confidence": "high | moderate | low"
}}

Identify the most significant 3-8 relationships. Return only valid JSON array."""

    data = llm_call_with_retry(prompt, settings.analysis_model, max_tokens=2000)
    relationships = []
    for r in data:
        # Validate relationship_type
        rt = r.get("relationship_type", "complex")
        try:
            r["relationship_type"] = RelationshipType(rt)
        except ValueError:
            r["relationship_type"] = RelationshipType.COMPLEX
        relationships.append(RelationshipAnalysis(**r))

    return relationships


def analyze_themes(job_id: str) -> List[ThemeAnalysis]:
    """Identify recurring themes and motifs."""
    context = build_sample_context(job_id, "theme motif recurring symbol meaning", n=15)

    prompt = f"""You are an expert literary analyst identifying themes and motifs in a novel.

Relevant passages:
{context}

Task: Identify the major themes and recurring motifs in this novel. A theme is a central idea; a motif is a recurring element (image, phrase, situation) that reinforces the theme.

Respond with a JSON array. Each element must match:
{{
  "theme": "Name of the theme (e.g., 'Loss and Grief', 'Power and Corruption')",
  "description": "2-3 sentence explanation of how this theme manifests in the novel",
  "motifs": ["recurring motif 1", "recurring motif 2"],
  "supporting_passages": [
    {{
      "text": "short quote or paraphrase that illustrates this theme",
      "page_reference": "p.X or null",
      "relevance": "how this passage supports the theme interpretation"
    }}
  ],
  "prevalence": "central | significant | minor"
}}

Identify 3-6 themes. Use interpretive language like 'the text suggests', 'appears to explore'. Return only valid JSON array."""

    data = llm_call_with_retry(prompt, settings.analysis_model, max_tokens=2000)
    return [ThemeAnalysis(**t) for t in data]


_ROMANCE_KEYWORDS = {"romance", "love", "romantic", "contemporary romance", "historical romance",
                     "paranormal romance", "dark romance", "erotic", "chick lit", "women's fiction"}
_FANTASY_KEYWORDS = {"fantasy", "magic", "supernatural", "paranormal", "urban fantasy",
                     "epic fantasy", "high fantasy", "fairy", "myth"}
_THRILLER_KEYWORDS = {"thriller", "mystery", "crime", "suspense", "detective", "noir", "horror"}


MAX_TROPES_IN_PROMPT = 90  # keeps total request safely under 12K TPM


def _select_tropes_for_genre(job_id: str, genre: str) -> List[Dict]:
    """Return a genre-aware trope subset capped at MAX_TROPES_IN_PROMPT."""
    import random

    genre_lower = genre.lower()
    classic = TROPE_LIBRARY[:25]
    rest = TROPE_LIBRARY[25:]

    is_romance = any(k in genre_lower for k in _ROMANCE_KEYWORDS)

    rng = random.Random(job_id)
    slots = MAX_TROPES_IN_PROMPT - len(classic)

    if is_romance:
        # Prioritise romance-specific tropes, then fill any remaining slots from classics pool
        romance = [t for t in rest]  # all non-classic tropes are romance-oriented
        selected_rest = rng.sample(romance, min(slots, len(romance)))
    else:
        selected_rest = rng.sample(rest, min(slots, len(rest)))

    return classic + selected_rest


def analyze_tropes(job_id: str, characters: List[CharacterAnalysis], overview: Optional[NovelOverview] = None) -> List[TropeAnalysis]:
    """Detect tropes from predefined library using genre-aware trope selection."""
    char_summary = "; ".join([
        f"{c.name} ({c.role}): {', '.join(c.defining_traits[:3])}"
        for c in characters[:5]
    ])

    genre = overview.genre_guess if overview else "unknown"
    novel_summary = overview.narrative_summary if overview else ""

    # Two targeted retrieval queries give broader evidence coverage
    context_structure = build_sample_context(job_id, "story structure conflict resolution character arc", n=8)
    context_relationships = build_sample_context(job_id, f"romance relationship love conflict {' '.join([c.name for c in characters[:3]])}", n=8)
    context = f"{context_structure}\n\n---\n\n{context_relationships}"

    selected = _select_tropes_for_genre(job_id, genre)
    trope_list = "\n".join([
        f"- {t['id']}: {t['name']} — {t['description']}"
        for t in selected
    ])

    prompt = f"""You are an expert literary analyst identifying narrative tropes in a novel.

Genre: {genre}
Novel summary: {novel_summary}
Character summary: {char_summary}

Relevant passages:
{context}

Available trope library (use ONLY these trope IDs):
{trope_list}

Task: Identify which tropes from the library appear in this novel. Prioritise tropes that match the genre and are directly supported by the passages above. You MUST identify multiple tropes (minimum 3, maximum 8). Each trope must be supported by textual evidence.

Respond with a JSON array. Each element must match:
{{
  "trope_name": "exact name from library",
  "trope_id": "exact id from library",
  "confidence": "strongly supported | moderately supported | weakly supported",
  "explanation": "2-3 sentences explaining how this trope appears in the text, using language like 'the text suggests' or 'evidence indicates'",
  "supporting_passages": [
    {{
      "text": "short quote or paraphrase from text",
      "page_reference": "p.X or null",
      "relevance": "how this illustrates the trope"
    }}
  ],
  "related_characters": ["Character names associated with this trope"]
}}

Return only valid JSON array."""

    data = llm_call_with_retry(prompt, settings.analysis_model, max_tokens=2000)
    return [TropeAnalysis(**t) for t in data]


def run_full_analysis(job_id: str, pages: List[Tuple[int, str]]) -> AnalysisReport:
    """Run the complete literary analysis pipeline."""
    logger.info(f"Starting full analysis for job {job_id}")

    # Get sample text for overview
    sample_pages = pages[:20]
    sample_text = "\n\n".join([text for _, text in sample_pages])

    # Run analyses
    logger.info("Analyzing overview...")
    overview = analyze_overview(job_id, sample_text)

    logger.info("Analyzing characters...")
    characters = analyze_characters(job_id)

    logger.info("Analyzing relationships...")
    relationships = analyze_relationships(job_id, characters)

    logger.info("Analyzing themes...")
    themes = analyze_themes(job_id)

    logger.info("Analyzing tropes...")
    tropes = analyze_tropes(job_id, characters, overview=overview)

    report = AnalysisReport(
        job_id=job_id,
        overview=overview,
        characters=characters,
        relationships=relationships,
        themes=themes,
        tropes=tropes,
        created_at=datetime.now(timezone.utc),
    )

    logger.info(f"Analysis complete for job {job_id}")
    return report
