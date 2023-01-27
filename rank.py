#!/usr/bin/env python3

import argparse
import difflib
import glob
import os
import pandas
import pathlib
import requests
import rich
import sys

from typing import Dict, List


# Globals
COL_COURSE_CODE = "Course Code"
COL_SECTION_GPA = "Section GPA"
COL_COURSE_GPA = "Course CPA*"

CWD = pathlib.Path(os.path.dirname(os.path.relpath(__file__)))
INSTRUCTOR_DIR = CWD.joinpath(".instructors")
TEMP_DIR = pathlib.Path("/tmp")

FMT_INSTRUCTOR_URL="https://stars.bilkent.edu.tr/evalreport/index.php?mode=ins&insId={}"


# Functions
def log(msg: str, level: str, color: str, style: str = "bold"):
    rich.print(f"[{style} {color}][{level}][/{style} {color}] {msg}")


def info(msg: str):
    log(msg, "info", "blue")


def warn(msg: str):
    log(msg, "warn", "yellow")


def error(msg: str):
    log(msg, "error", "error")


def title(s: str):
    rich.print(f"[bold magenta]{s}[/bold magenta]")


def report(report_title: str, result):
    rich.print(f"[bold green]{report_title}:[/bold green] {result}")


class Instructor:
    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url


class Report:
    def __init__(
            self,
            weight_of_section_gpa_gt_course_avg: float,
            weight_of_section_gpa_gt_3: float,
            weight_of_course_gpa_gt_3: float,
            avg_section_course_diff: float,
            instructor: Instructor
    ):
        self.weight_of_section_gpa_gt_course_avg = weight_of_section_gpa_gt_course_avg
        self.weight_of_section_gpa_gt_3 = weight_of_section_gpa_gt_3
        self.weight_of_course_gpa_gt_3 = weight_of_course_gpa_gt_3
        self.avg_section_course_diff = avg_section_course_diff
        self.instructor: Instructor = instructor

    def __lt__(self, other: "Report"):
        if self.avg_section_course_diff == other.avg_section_course_diff:
            return self.weight_of_section_gpa_gt_course_avg < other.weight_of_section_gpa_gt_course_avg

        return self.avg_section_course_diff < other.avg_section_course_diff

    def __eq__(self, other: "Report"):
        return self.avg_section_course_diff == other.avg_section_course_diff \
                and self.weight_of_section_gpa_gt_course_avg == other.weight_of_section_gpa_gt_course_avg

    def print(self, names_only: bool = False):
        if names_only:
            title(f"{self.instructor.name}")
            return

        title(f"{self.instructor.name}:")
        report("Weight of Section GPA > Course Avg", f"{self.weight_of_section_gpa_gt_course_avg:.2f}%")
        report("Weight of Section GPA > 3", f"{self.weight_of_section_gpa_gt_3:.2f}%")
        report("Weight of Course GPA > 3", f"{self.weight_of_course_gpa_gt_3:.2f}%")
        report("Average of Section GPA - Course Average", f"{self.avg_section_course_diff:.2f}")
        print()


def download_file(url: str, _decode: bool = False, _encoding: str = "utf-8") -> bytes | str | None:
    response = requests.get(url)
    if not response.ok:
        return None

    if _decode:
        return response.content.decode(_encoding)
    else:
        return response.content


def fetch_evaluation_data(instructor: Instructor, override: bool = False) -> bool:
    html_file = f"{instructor.name}.csv"
    instructor_data_file = INSTRUCTOR_DIR.joinpath(html_file)

    info(f"Fetching evaluation data for {instructor.name}")

    if os.path.exists(instructor_data_file) and not override:
        warn(f"Evaluation data for {instructor.name} already exists, skipping")
        return True

    html_data = download_file(instructor.url, _decode=True)
    if html_data is None:
        error(f"Could not download evaluation data from: {instructor.url}")
        return False

    instructor_data_file.parent.mkdir(parents=True, exist_ok=True)

    data = pandas.read_html(html_data)[0]
    data.to_csv(path_or_buf=instructor_data_file, index=False, sep="|",
                                          columns=(COL_COURSE_CODE, COL_SECTION_GPA, COL_COURSE_GPA))

    return True


def load_instructors_from_list(filename: str) -> List[Instructor]:
    instructors: List[Instructor] = []
    with open(filename, "r") as f:
        for line in f:
            name, insId = tuple(line.strip().split(";"))
            instructors.append(Instructor(name, FMT_INSTRUCTOR_URL.format(insId)))

    return instructors


def load_instructors_from_existing() -> Dict[Instructor, pandas.DataFrame]:
    if not os.path.exists(INSTRUCTOR_DIR) or not os.path.isdir(INSTRUCTOR_DIR):
        error(f"Folder {INSTRUCTOR_DIR} does not exists or is a file")
        return {}

    pattern = fr"{INSTRUCTOR_DIR}/*.csv"
    file_list = [pathlib.Path(file) for file in glob.glob(pattern)]

    instructors: Dict[Instructor, pandas.DataFrame] = {}
    for file in file_list:
        data = pandas.read_csv(filepath_or_buffer=file, sep="|")
        instructor = Instructor(file.stem, data)
        instructors[instructor] = data

    return instructors


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", dest="instructor_list", required=False, default=None,
                        help="File containing InstructorName;InstructorId pair")
    parser.add_argument("-c", "--course", dest="course", required=True,
                        help="Course to grep from instructor evaluations")
    parser.add_argument("-o", "--override", dest="override", required=False, default=False, action="store_true",
                        help="Override existing instructor evaluation data")
    parser.add_argument("-n", "--names", dest="names_only", required=False, default=False, action="store_true",
                        help="Only show names")

    return parser.parse_args(sys.argv[1:])


def main():
    args = parse_args()

    if args.instructor_list is not None:
        info("Instructor file is specified. Will try to fetch data for all and save them")

        keys = load_instructors_from_list(args.instructor_list)
        for key in keys:
            fetch_evaluation_data(key, args.override)

    instructors: Dict[Instructor, pandas.DataFrame] = load_instructors_from_existing()
    instructor_reports: List[Report] = []

    for instructor, data in instructors.items():
        course_data = data[data[COL_COURSE_CODE] == args.course]
        if len(course_data) == 0:
            continue

        section_gpas: pandas.Series = course_data[COL_SECTION_GPA]
        course_gpas: pandas.Series = course_data[COL_COURSE_GPA]

        section_gpa_gt_course: pandas.Series = section_gpas[section_gpas > course_gpas]
        section_gpa_gt_3: pandas.Series = section_gpas[section_gpas > 3]
        course_gpa_gt_3: pandas.Series = course_gpas[course_gpas > 3]
        section_course_diff: pandas.Series = section_gpas - course_gpas

        weight_of_section_gpa_gt_course_avg = len(section_gpa_gt_course)*100/len(course_data)
        weight_of_section_gpa_gt_3 = len(section_gpa_gt_3)*100/len(course_data)
        weight_of_course_gpa_gt_3 = len(course_gpa_gt_3)*100/len(course_data)
        avg_section_course_diff = section_course_diff.mean()

        rep = Report(weight_of_section_gpa_gt_course_avg,
                     weight_of_section_gpa_gt_3,
                     weight_of_course_gpa_gt_3,
                     avg_section_course_diff,
                     instructor)

        instructor_reports.append(rep)

    for rep in sorted(instructor_reports, reverse=True):
        rep.print(args.names_only)


if __name__ == "__main__":
    main()
