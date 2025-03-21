import requests
from bs4 import BeautifulSoup
import json
import re
from urllib.parse import urljoin


def scrape_jeopardy_game(game_id):
    """
    Scrapes a specific Jeopardy game from j-archive.com

    Args:
        game_id (int): The ID of the game to scrape

    Returns:
        list: A list of dictionaries containing question data, or None if scraping fails
    """
    # Construct the URL for the specific game
    url = f"https://www.j-archive.com/showgame.php?game_id={game_id}"
    print(f"Scraping URL: {url}")

    # Set a user agent to avoid being blocked by the website
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    # Fetch the webpage
    response = requests.get(url, headers=headers)

    # Check if the request was successful
    if response.status_code != 200:
        print(f"Failed to retrieve the page: {response.status_code}")
        return None

    # Parse the HTML content
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find all cells with class="clue" which contain the questions
    # These appear in all three game boards (Jeopardy, Double Jeopardy, Final Jeopardy)
    clue_cells = soup.find_all('td', class_='clue')
    print(f"Found {len(clue_cells)} clue cells")

    questions = []
    question_number = 1

    # Process each clue cell
    for clue_cell in clue_cells:
        # Find the question text element within this clue cell
        question_td = clue_cell.find('td', class_='clue_text')

        # Skip if no question text found in this cell
        if not question_td:
            continue

        # Get the unique ID of this question (needed to find the answer)
        if not question_td.get('id'):
            continue

        clue_id = question_td['id']

        # Find the corresponding answer element using the ID pattern
        # The answer ID is the question ID with "_r" appended
        answer_td_id = f"{clue_id}_r"
        answer_td = soup.find('td', id=answer_td_id)

        # Skip if no answer element found
        if not answer_td:
            continue

        # Extract question text and images
        question_text = ''
        images = []

        # Process each element within the question text
        for content in question_td.contents:
            if isinstance(content, str):
                # Plain text content
                question_text += content
            elif content.name == 'a' and content.get('href'):
                # This is a linked word/phrase with an image
                img_url = content.get('href')
                img_text = content.text
                if img_url and img_text:
                    # Convert relative URLs to absolute URLs
                    full_img_url = urljoin("https://www.j-archive.com/", img_url)
                    images.append({"word": img_text, "url": full_img_url})
                    question_text += img_text  # Include the linked text in the question
            else:
                # Other HTML elements - extract their text
                if hasattr(content, 'text'):
                    question_text += content.text

        # Clean up question text by removing extra whitespace
        question_text = question_text.strip()

        # Extract answer from the answer element
        # The correct response is within an <em> tag with class="correct_response"
        answer_elem = answer_td.find('em', class_='correct_response')
        answer = answer_elem.text.strip() if answer_elem else ""

        # Create a dictionary with the question data
        question_data = {
            "question_number": str(question_number),
            "answer": answer,
            "images": images,
            "question_text": question_text
        }

        # Add this question to our results
        questions.append(question_data)
        question_number += 1

    print(f"Successfully extracted {len(questions)} questions")
    return questions


def save_to_json(questions, game_id):
    """
    Saves the extracted questions to a JSON file

    Args:
        questions (list): List of question dictionaries
        game_id (int): Game ID used for the filename
    """
    # Create filename based on game ID
    filename = f"jeopardy_game_{game_id}.json"

    # Write the questions to a JSON file with nice formatting
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(questions, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(questions)} questions to {filename}")

    # Print a sample question for verification
    if questions:
        print("\nSample question:")
        print(json.dumps(questions[0], indent=2, ensure_ascii=False))


def main():
    """
    Main function to run the scraper
    """
    # Game ID to scrape (can be modified or made into a command line argument)
    game_id = 4972

    # Scrape the game
    questions = scrape_jeopardy_game(game_id)

    # Save results if questions were found
    if questions:
        save_to_json(questions, game_id)
    else:
        print("No questions were extracted. Check the URL and page structure.")


# Entry point for the script
if __name__ == "__main__":
    main()