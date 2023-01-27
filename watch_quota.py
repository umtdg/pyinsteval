#!/usr/bin/env python3

from argparse import ArgumentParser
from datetime import datetime
from sys import argv
from time import sleep

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

parser = ArgumentParser()
parser.add_argument("-c", "--course", dest="course", required=True)
parser.add_argument("-s", "--section", nargs="+", dest="sections", required=True)
parser.add_argument("-i", "--interval", type=int, dest="interval", required=False, default=60)

args = parser.parse_args(argv[1:])

interval = args.interval
course = args.course
sections = [section.zfill(3) for section in args.sections]
section_quota_cache = {}
url = f"https://stars.bilkent.edu.tr/homepage/offerings.php?COURSE_CODE={course.split(' ')[0]}"


print(f"Course: {course}")
print(f"Sections: {sections}")

driver_opts = Options()
driver_opts.headless = True
driver_opts.set_preference("detach", True)

driver = webdriver.Firefox(options=driver_opts)
driver.get(url)

max_tries = 10
tries = 0
try:
    while True:
        course_table = None
        while True:
            try:
                if tries == max_tries:
                    print("Could not load page")
                    driver.get(url)
                    tries = 0

                course_table = driver.find_element(By.ID, "courses")
                break
            except:
                tries += 1
                sleep(1)

        try:
            course_elem = WebDriverWait(driver, 1000000).until(EC.element_to_be_clickable((By.ID, course)))
            row_course_code = course_elem.find_elements(By.TAG_NAME, "td")[0]
            assert row_course_code.text == course
            row_course_code.click()
        except Exception as e:
            print(f"Could not click {course}: {e}")
            driver.close()
            exit()

        has_changed_quota = False
        for section in sections:
            course_section = f"{course}-{section}"

            try:
                section_row = driver.find_element(By.ID, course_section)
            except:
                print(f"Could not found section {course_section}")
                driver.close()
                exit()

            section_cols = section_row.find_elements(By.TAG_NAME, "td")
            assert section_cols[0].text == course_section

            if section in section_quota_cache:
                old_quota = section_quota_cache[section]
            else:
                old_quota = ""

            section_quota_cache[section] = section_cols[-2].text

            if old_quota != section_quota_cache[section]:
                print("[{}] Available quota in {}: {}".format(
                    datetime.now().strftime('%m.%d.%Y, %H:%M:%S'),
                    course_section,
                    section_quota_cache[section]
                ))
                has_changed_quota = True

        if not has_changed_quota:
            print(f"Quotas are unchanged in the interval of {interval} second(s)")

        sleep(interval)
        driver.refresh()
        print("------------------------")
finally:
    driver.close()
