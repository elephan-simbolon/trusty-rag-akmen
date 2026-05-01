#!/usr/bin/env bash
# Ingest all 21 consulting books into Qdrant.
# Case_in_Point_11 already ingested (379 chunks) — skipped.
# Run from project root: bash scripts/ingest_consulting.sh

set -e

BOOKS=(
    "Case_in_Point_9_-_Marc_P_Cosentino.pdf|Case in Point 9|Marc P. Cosentino"
    "Case_Interview_Secrets__A_Former_McKinsey_-_Victor_Cheng.pdf|Case Interview Secrets|Victor Cheng"
    "Flawless_Consulting_-_Peter_Block.pdf|Flawless Consulting|Peter Block"
    "Leading_with_the_McKinsey_7S_Framework_-_The_LeadXL_Company.pdf|Leading with the McKinsey 7S Framework|The LeadXL Company"
    "McKinsey mind - Ethan m raisiel.pdf|The McKinsey Mind|Ethan M. Rasiel"
    "McKinsey_and_Company_-_WetFeet.pdf|McKinsey and Company|WetFeet"
    "McKinsey-style_Elevator_Speech__Concise_reporting_and_communication_tips_-_River_Lee.pdf|McKinsey-style Elevator Speech|River Lee"
    "Perspective_on_McKinsey_-_Marvin_Bower.pdf|Perspective on McKinsey|Marvin Bower"
    "Rewired_-_Eric_Lamarre.pdf|Rewired|Eric Lamarre"
    "Strategy_Beyond_the_Hockey_Stick_-_Chris_Bradley.pdf|Strategy Beyond the Hockey Stick|Chris Bradley"
    "The McKinsey Way - Ethan M Rasiel.pdf|The McKinsey Way|Ethan M. Rasiel"
    "The_1_Conquer_Your_Consulting_Case_Interview_-_Florian_Smeritschnig.pdf|Conquer Your Consulting Case Interview|Florian Smeritschnig"
    "The_Firm__The_Story_of_McKinsey_and_Its_Se_-_Duff_McDonald.pdf|The Firm: The Story of McKinsey|Duff McDonald"
    "The_Lords_of_Strategy_-_Walter_Kiechel_III.pdf|The Lords of Strategy|Walter Kiechel III"
    "The_McKinsey_Edge__Success_Principles_from_-_Shu_Hattori.pdf|The McKinsey Edge|Shu Hattori"
    "The_McKinsey_Engagement_A_Powerful_Toolkit_for_More_Efficient_and_Effective_Team_Problem_Solving_-_Paul_Friga.pdf|The McKinsey Engagement|Paul Friga"
    "The_Mind_Of_Strategist_-_Kenich_Ohmae.pdf|The Mind of the Strategist|Kenichi Ohmae"
    "The_Minto_Pyramid_Principle_-_Barbara_Minto.pdf|The Minto Pyramid Principle|Barbara Minto"
    "Valuation_-_McKinsey.pdf|Valuation|McKinsey & Company"
    "When_McKinsey_Comes_to_Town_The_Hidden_Influence_of_the_Worlds_Most_Powerful_Consulting_Firm_-_Walt_Bogdanich.pdf|When McKinsey Comes to Town|Walt Bogdanich"
)

TOTAL=${#BOOKS[@]}
SUCCESS=0
FAILED=()

for ENTRY in "${BOOKS[@]}"; do
    IFS='|' read -r FILE TITLE AUTHOR <<< "$ENTRY"
    PDF="data/pdfs/consulting/$FILE"

    echo ""
    echo "============================================================"
    echo "[$((SUCCESS + 1 + ${#FAILED[@]}))/$TOTAL] $TITLE — $AUTHOR"
    echo "============================================================"

    if uv run python scripts/ingest.py \
        "$PDF" \
        --source-domain consulting \
        --book-title "$TITLE" \
        --author "$AUTHOR" \
        --no-vlm; then
        SUCCESS=$((SUCCESS + 1))
    else
        echo "FAILED: $FILE"
        FAILED+=("$FILE")
    fi
done

echo ""
echo "============================================================"
echo "DONE: $SUCCESS/$TOTAL books ingested successfully"
if [ ${#FAILED[@]} -gt 0 ]; then
    echo "FAILED books:"
    for F in "${FAILED[@]}"; do echo "  - $F"; done
fi
echo "============================================================"
