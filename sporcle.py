from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import json


def scrape_sporcle():
    """
    Scrapes the Sporcle quiz 'Actors in Three Forms of Visual Media II'.

    This function handles:
    1. Setting up the WebDriver
    2. Navigating to the quiz page
    3. Accepting cookie consent
    4. Starting and giving up the quiz
    5. Scraping data from all quiz slides
    6. Saving the results to a JSON file

    Returns:
        None. Results are saved to 'sporcle_results.json'
    """
    # Setup WebDriver with additional options for better performance and reliability
    options = Options()
    options.add_argument("--start-maximized")  # Maximize browser window
    options.add_argument("--disable-notifications")  # Prevent notification popups
    # Disable images to speed up loading and reduce interference
    options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})

    # Initialize the Chrome WebDriver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    # Navigate to the target Sporcle quiz
    url = "https://www.sporcle.com/games/ghcgh/actors-in-three-forms-of-visual-media-ii"
    driver.get(url)

    # Wait for page to fully load
    time.sleep(5)

    # ----- HANDLE COOKIE CONSENT DIALOG -----
    try:
        # Find the cookie consent iframe by its ID
        iframe = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "sp_message_iframe_1198624"))
        )
        print("Cookie consent iframe found, switching to it...")
        driver.switch_to.frame(iframe)

        # Look for and click the Accept button within the iframe
        accept_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.last-focusable-el"))
        )
        print("Found Accept button within iframe, clicking...")
        accept_button.click()

        # Return focus to the main page content
        driver.switch_to.default_content()
        print("Switched back to main content")
        time.sleep(3)
    except Exception as e:
        # If the standard approach fails, try alternative methods
        print(f"Error handling cookie consent iframe: {e}")
        driver.switch_to.default_content()

        # Try JavaScript method to dismiss cookies by hiding elements
        try:
            driver.execute_script("""
                // Try to remove common cookie consent elements
                var elements = document.querySelectorAll('[id*="cookie"], [class*="cookie"], [id*="consent"], [class*="consent"]');
                for(var i=0; i<elements.length; i++){
                    elements[i].style.display = 'none';
                }
            """)
            time.sleep(2)
        except Exception as js_error:
            print(f"JavaScript attempt failed: {js_error}")

    # ----- START THE QUIZ -----
    try:
        # Wait for and click the Play button
        play_button = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.ID, "button-play"))
        )
        # Use JavaScript click to bypass potential overlay issues
        driver.execute_script("arguments[0].click();", play_button)
        print("Play button clicked!")
        time.sleep(5)  # Wait for game to initialize
    except Exception as e:
        print(f"Play button click failed: {e}")
        driver.quit()
        return

    # ----- GIVE UP THE QUIZ TO REVEAL ANSWERS -----
    try:
        # Find and click the Give Up button to reveal all answers
        give_up_button = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.ID, "giveUp"))
        )
        driver.execute_script("arguments[0].click();", give_up_button)
        print("Give Up button clicked!")

        # Some quizzes require confirmation after clicking Give Up
        try:
            confirm_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".gameConfirmText button"))
            )
            driver.execute_script("arguments[0].click();", confirm_button)
            print("Confirm button clicked!")
        except Exception as e:
            print(f"No confirm button found, may have been auto-confirmed: {e}")

        time.sleep(8)  # Longer wait after giving up to ensure all answers are loaded
    except Exception as e:
        print(f"Give Up button not found: {e}")
        driver.quit()
        return

    # ----- REMOVE OVERLAYS AND PREPARE FOR SCRAPING -----
    # Use JavaScript to remove elements that might interfere with navigation
    driver.execute_script("""
        // Remove potential obstructions like ads, overlays, banners
        var obstructions = document.querySelectorAll('[class*="ad"], [id*="ad"], [class*="overlay"], [id*="overlay"], [class*="banner"], [id*="banner"]');
        for(var i=0; i<obstructions.length; i++){
            if(obstructions[i]) obstructions[i].remove();
        }

        // Make navigation elements more accessible by increasing z-index
        var navElements = document.querySelectorAll('#rightNav, #leftNav, #thumbBar');
        for(var i=0; i<navElements.length; i++){
            if(navElements[i]) {
                navElements[i].style.zIndex = '10000';
                navElements[i].style.position = 'relative';
            }
        }
    """)

    # ----- DETERMINE TOTAL QUESTION COUNT -----
    try:
        # Count the number of thumbnail elements to determine how many questions exist
        thumbs = driver.find_elements(By.CSS_SELECTOR, "[id^='name']")
        total_questions = len(thumbs)
        print(f"Detected {total_questions} questions in the thumb bar")
    except Exception as e:
        print(f"Could not determine question count: {e}")
        total_questions = 20  # Default to 20 if count detection fails

    # Take a screenshot for debugging
    # driver.save_screenshot("after_give_up.png")

    # ----- NAVIGATE TO FIRST SLIDE -----
    try:
        # Try to click on the first thumbnail to start at the beginning
        first_thumb = driver.find_element(By.ID, "name0")  # First thumbnail
        driver.execute_script("arguments[0].click();", first_thumb)
        print("Navigated to first slide")
        time.sleep(2)
    except Exception as e:
        print(f"Could not navigate to first slide via thumbnail: {e}")

        # Alternative: try clicking leftNav repeatedly to reach the first slide
        try:
            left_nav = driver.find_element(By.ID, "leftNav")
            for _ in range(5):  # Click left 5 times to ensure we're at the start
                driver.execute_script("arguments[0].click();", left_nav)
                time.sleep(0.5)
            print("Navigated to first slide via leftNav")
        except Exception as e2:
            print(f"Left navigation failed: {e2}")

    # Initialize array to store quiz results
    results = []

    # ----- EXTRACT DATA FROM EACH QUESTION -----
    for i in range(total_questions):
        try:
            # Take a screenshot of each slide for debugging purposes
            # driver.save_screenshot(f"slide_{i + 1}.png")

            # Set question number (1-indexed for user readability)
            question_number = i + 1

            # ----- EXTRACT ANSWER TEXT -----
            try:
                answer_element = WebDriverWait(driver, 5).until(
                    EC.visibility_of_element_located((By.ID, "resultText"))
                )
                answer = answer_element.text.strip()
            except Exception:
                answer = "Could not extract answer"

            # ----- EXTRACT IMAGE URL -----
            try:
                image_element = driver.find_element(By.ID, "currimage")
                image_url = image_element.get_attribute("src")
            except Exception:
                image_url = ""

            # ----- EXTRACT EXTRA TEXT (media appearances) -----
            try:
                extra_text_element = driver.find_element(By.ID, "extraText")
                extra_text = extra_text_element.text.strip()
            except Exception:
                extra_text = ""

            # Store the extracted data
            results.append({
                "question_number": str(question_number),
                "answer": answer,
                "image_url": image_url,
                "extra_text": extra_text
            })

            print(f"Extracted slide {i + 1}: {answer} - {extra_text}")

            # ----- NAVIGATE TO NEXT SLIDE -----
            # Only attempt navigation if not on the last slide
            if i < total_questions - 1:
                # METHOD 1: Try to click the specific thumbnail for the next question
                try:
                    next_thumb = driver.find_element(By.ID, f"name{i + 1}")
                    driver.execute_script("arguments[0].click();", next_thumb)
                    time.sleep(1)
                except Exception as thumb_error:
                    print(f"Could not click thumbnail for slide {i + 2}: {thumb_error}")

                    # METHOD 2: If thumbnail click fails, try the right arrow
                    try:
                        right_nav = driver.find_element(By.ID, "rightNav")
                        # Use JavaScript click to bypass any overlay issues
                        driver.execute_script("arguments[0].click();", right_nav)
                        time.sleep(1)
                    except Exception as nav_error:
                        print(f"Right navigation failed for slide {i + 1}: {nav_error}")

                        # METHOD 3: Last resort - try to navigate using keyboard arrow keys
                        try:
                            action = ActionChains(driver)
                            action.send_keys('\ue014')  # Right arrow key
                            action.perform()
                            time.sleep(1)
                        except Exception as key_error:
                            print(f"Keyboard navigation failed: {key_error}")

        except Exception as e:
            print(f"Error processing slide {i + 1}: {e}")
            # Continue to next slide even if current one fails

    # Close the browser when done
    driver.quit()

    # ----- SAVE RESULTS TO JSON FILE -----
    with open("sporcle_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)

    print(f"Results saved to sporcle_results.json with {len(results)} entries")

    # ----- VALIDATE RESULTS: CHECK FOR DUPLICATES -----
    # Extract just the answers for duplicate detection
    answers = [r["answer"] for r in results]
    unique_answers = set(answers)

    # If there are fewer unique answers than total answers, we have duplicates
    if len(unique_answers) < len(answers):
        print(f"WARNING: Only {len(unique_answers)} unique answers out of {len(answers)} total")
        print("Duplicate detection:")

        # Count occurrences of each answer
        answer_counts = {}
        for answer in answers:
            if answer in answer_counts:
                answer_counts[answer] += 1
            else:
                answer_counts[answer] = 1

        # Report any duplicates
        for answer, count in answer_counts.items():
            if count > 1:
                print(f"  '{answer}' appears {count} times")
    else:
        print("All answers are unique!")


if __name__ == "__main__":
    scrape_sporcle()