import base64
import csv
import tempfile
import traceback
import os
import subprocess
from celery import Celery


# Celery ----------------------------------------------------------------------

celery = Celery(
    'swabseq-analysis-celery',
    backend=os.environ.get('CELERY_RESULT_BACKEND', None),
    broker=os.environ.get('CELERY_BROKER_URL', None),
)

# celery.conf.update(app.config)


# Analysis --------------------------------------------------------------------

count_table_fields = {
    'plateIndex': 'Plate_384_Number',
    'plateCell': 'Sample_Well',
    'marker1': 'index',
    'marker2': 'index2',
    'classification': 'classification',
}

def b64encode_file(filepath):
    with open(filepath, "r") as input_file:
        return base64.b64encode(input_file.read()).encode()

def read_csv_as_dict_list(filepath):
    with open(filepath, "r") as csv_file:
        csv_reader = csv.DictReader(csv_file)
        return [x for x in csv_reader]

def rename_fields(original, fields):
    return {
        new_field: original[original_field]
        for new_field, original_field
        in fields.items()
        if original_field in original
    }

@celery.task()
def run_analysis(basespace_id):
    try:
        # Run R script and zip results to generate temp file
        with tempfile.TemporaryDirectory(prefix=f"{basespace_id}-results-", dir=os.getcwd()) as rundir:
            # rundir = tempfile.TemporaryDirectory(prefix=f"{basespace_id}-results-", dir=os.getcwd()).name
            os.makedirs(os.path.join(rundir, "out"))

            subprocess.call([
                "Rscript",
                "--vanilla",
                "code/countAmpliconsAWS.R",
                "--rundir",
                f"{rundir}/",
                "--basespaceID",
                basespace_id,
                "--threads",
                f"{os.environ.get('RSCRIPT_THREADS', '8')}"
            ])

            count_table_raw = read_csv_as_dict_list(f"{rundir}/countTable.csv")

            return {
                'status': 'ready',
                'basespace_id': basespace_id,
                'results': [rename_fields(row, count_table_fields) for row in count_table_raw],
                'attachments': {
                    'LIMS_results.csv': b64encode_file(f"{rundir}/LIMS_results.csv"),
                    'run_info.csv': b64encode_file(f"{rundir}/run_info.csv"),
                    f"{basespace_id}.pdf": b64encode_file(f"{rundir}/{basespace_id}.pdf"),
                    'countTable.csv': b64encode_file(f"{rundir}/countTable.csv"),
                    'SampleSheet.csv': b64encode_file(f"{rundir}/SampleSheet.csv"),
                },
            }
    except Exception as ex:
        ex_str = traceback.format_exc()
        print(ex_str)
        return {
            'status': 'failed',
            'error': ex_str,
        }
