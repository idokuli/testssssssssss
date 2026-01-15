from flask import Blueprint, request, redirect, url_for, session, render_template, flash
from s3_service import S3Service

s3_bp = Blueprint('s3', __name__)

def get_worker():
    """Helper to initialize the S3 Service from session data."""
    return S3Service(
        session.get('access'), 
        session.get('secret'), 
        session.get('region')
    )

@s3_bp.route('/')
def s3_index():
    if 'access' not in session:
        return redirect(url_for('s3.s3_login'))
    
    try:
        worker = get_worker()
        _, files = worker.list_files(session['bucket'])
        versioning = worker.get_versioning_status(session['bucket'])
        return render_template('s3_explorer.html', 
                               files=files, 
                               bucket_name=session['bucket'],
                               versioning=versioning)
    except Exception as e:
        flash(f"S3 Error: {str(e)}")
        return render_template('s3_explorer.html', files=[], bucket_name="Error", versioning="Unknown")

@s3_bp.route('/login', methods=['GET', 'POST'])
def s3_login():
    if request.method == 'POST':
        session.update({
            'access': request.form.get('access'),
            'secret': request.form.get('secret'),
            'region': request.form.get('region', 'us-east-1'),
            'bucket': request.form.get('bucket')
        })
        return redirect(url_for('s3.s3_index'))
    
    return render_template('s3_login.html')

@s3_bp.route('/upload', methods=['POST'])
def upload_file():
    file = request.files.get('file')
    if file:
        filename = file.filename.lower()
        # Auto-Prefix Logic based on file type
        if filename.endswith(('.png', '.jpg', '.jpeg', '.gif')):
            prefix = "images/"
        elif filename.endswith(('.pdf', '.doc', '.docx', '.txt')):
            prefix = "documents/"
        else:
            prefix = "others/"
        
        try:
            full_key = f"{prefix}{file.filename}"
            get_worker().upload_file(session['bucket'], file, full_key)
            flash(f"Auto-categorized as {prefix}")
        except Exception as e:
            flash(f"Upload Error: {str(e)}")
    return redirect(url_for('s3.s3_index'))

@s3_bp.route('/set_versioning', methods=['POST'])
def set_versioning():
    target = request.form.get('status')
    try:
        get_worker().set_versioning(session['bucket'], target)
        flash(f"Versioning updated: {target}")
    except Exception as e:
        flash(f"Versioning Error: {str(e)}")
    return redirect(url_for('s3.s3_index'))

@s3_bp.route('/apply_policy')
def apply_policy():
    try:
        get_worker().apply_lifecycle(session['bucket'])
        flash("30-Day Policy Applied Successfully")
    except Exception as e:
        flash(f"Policy Error: {str(e)}")
    return redirect(url_for('s3.s3_index'))

@s3_bp.route('/history/<path:filename>')
def file_history(filename):
    try:
        v_list = get_worker().get_file_versions(session['bucket'], filename)
        return render_template('s3_history.html', filename=filename, versions=v_list)
    except Exception as e:
        flash(f"History Error: {str(e)}")
        return redirect(url_for('s3.s3_index'))

@s3_bp.route('/download/<path:filename>')
def download_file(filename):
    return redirect(get_worker().get_url(session['bucket'], filename))

@s3_bp.route('/delete/<path:filename>', methods=['POST'])
def delete_file(filename):
    try:
        get_worker().delete_object(session['bucket'], filename)
        flash(f"Deleted {filename}")
    except Exception as e:
        flash(f"Delete Error: {str(e)}")
    return redirect(url_for('s3.s3_index'))

@s3_bp.route('/logout')
def s3_logout():
    for key in ['access', 'secret', 'region', 'bucket']:
        session.pop(key, None)
    return redirect(url_for('hub'))