import base64
import csv
import tempfile
import subprocess
from flask import abort, request, send_file
from flask_restx import Resource, fields, Namespace

from authorization import requires_auth


api = Namespace('swabseq', description='Operations for Swabseq sequence data analysis.', path='/')


swabseq_input = api.model('SwabseqInput', {
    'basespace': fields.String()
})
swabseq_result = api.model('SwabseqResult', {})
swabseq_attachments = api.model('SwabseqAttachments', {
    'LIMS_results.csv': fields.String(),
    'run_info.csv': fields.String(),
    'countTable.csv': fields.String(),
    'SampleSheet.csv': fields.String(),
})
swabseq_output = api.model('SwabseqOutput', {
    'id': fields.String(),
    'results': fields.List(fields.Nested(swabseq_result)),
    'attachments': fields.Nested(swabseq_attachments),
})


def b64encode_file(filepath):
    with open(filepath, "r") as input_file:
        return base64.b64encode(input_file.read()).encode()

def read_csv_as_dict_list(filepath):
    with open(f"{rundir}/countTable.csv") as csv_file:
        csv_reader = csv.DictReader(csv_file)
        return [x for x in csv_reader]


@api.route('/swabseq/<string:basespace_id>')
class RunsResource(Resource):
    @api.doc(security='token', body=swabseq_input, params={'basespace_id': basespace_id_param})
    @requires_auth
    def get(self, basespace_id):
        if not basespace_id:
            abort(400, description='Error. Not a valid Basespace run name string')
            return

        # Run R script and zip results to generate temp file
        with tempfile.TemporaryDirectory(prefix=f"{basespace_id}-results-") as rundir:
            subprocess.call([
                "Rscript",
                "--vanilla",
                "swabseq_api/code/countAmpliconsAWS.R",
                "--rundir",
                f"{rundir}/",
                "--basespaceID",
                basespace_id,
                "--threads",
                f"{app.config['RSCRIPT_THREADS']}"
            ])

            return {
                'id': basespace_id,
                'results': read_csv_as_dict_list(f"{rundir}/countTable.csv"),
                'attachments': {
                    'LIMS_results.csv': b64encode_file(f"{rundir}/LIMS_results.csv"),
                    'run_info.csv': b64encode_file(f"{rundir}/run_info.csv"),
                    f"{basespace_id}.pdf": b64encode_file(f"{rundir}/{basespace_id}.pdf"),
                    'countTable.csv': b64encode_file(f"{rundir}/countTable.csv"),
                    'SampleSheet.csv': b64encode_file(f"{rundir}/SampleSheet.csv"),
                },
            }
