#!/usr/bin/env python3

import os
import sys
import subprocess
import matplotlib.pyplot as plt
from glob import glob
from tqdm import tqdm
from colorizers import *
import shutil
import time
import re
import argparse

def get_unique_stamp():
    """Generate a unique timestamp-based string."""
    return str(int(time.time()))

def count_frames(video_path):
    """Count the total number of frames in the video using FFmpeg."""
    command = f'ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of default=nokey=1:noprint_wrappers=1 "{video_path}"'
    try:
        frame_count = int(subprocess.check_output(command, shell=True).strip())
    except subprocess.CalledProcessError:
        frame_count = 0
        print(f"Could not count frames in {video_path}. Defaulting to 0.")
    return frame_count

def extract_frames(input_video, frame_dir):
    """Extract frames from the video using FFmpeg with a progress bar."""
    frame_count = count_frames(input_video)
    if not os.path.exists(frame_dir):
        os.makedirs(frame_dir)
    
    command = [
        'ffmpeg', '-i', input_video, '-q:v', '2', f'{frame_dir}/frame_%04d.jpg', '-y'
    ]
    process = subprocess.Popen(command, stderr=subprocess.PIPE, universal_newlines=True)

    # Regex to capture the current frame being processed
    frame_pattern = re.compile(r'frame=\s*(\d+)')
    
    # Progress bar for frame extraction
    with tqdm(total=frame_count, desc="Extracting frames") as pbar:
        while True:
            line = process.stderr.readline()
            if not line:
                break
            # Search for the frame number in the output
            match = frame_pattern.search(line)
            if match:
                current_frame = int(match.group(1))
                pbar.update(current_frame - pbar.n)
                
    process.wait()

def colorize_image(img_path, model='eccv16', use_gpu=False, save_prefix='saved'):
    """Colorize a single image with the specified model."""
    if model == 'eccv16':
        colorizer = eccv16(pretrained=True).eval()
    elif model == 'siggraph17':
        colorizer = siggraph17(pretrained=True).eval()
    else:
        raise ValueError("Invalid model name. Choose 'eccv16' or 'siggraph17'.")

    if use_gpu:
        colorizer.cuda()

    img = load_img(img_path)
    (tens_l_orig, tens_l_rs) = preprocess_img(img, HW=(256, 256))
    if use_gpu:
        tens_l_rs = tens_l_rs.cuda()

    out_img = postprocess_tens(tens_l_orig, colorizer(tens_l_rs).cpu())
    plt.imsave(f'{save_prefix}_{model}.png', out_img)

def colorize_frames(input_dir, output_dir, model='eccv16', use_gpu=False):
    """Colorize extracted frames using the specified model."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    frame_files = sorted(glob(input_dir + '/frame_*.jpg'))
    total_frames = len(frame_files)

    # Progress bar for colorizing frames
    for frame in tqdm(frame_files, desc="Colorizing frames", total=total_frames):
        output_file_prefix = os.path.join(output_dir, os.path.basename(frame).replace('frame_', 'colorized_frame_').split('.')[0])
        colorize_image(frame, model=model, use_gpu=use_gpu, save_prefix=output_file_prefix)

def assemble_video(frame_dir, output_video, model='eccv16', framerate=24):
    """Reassemble frames into a video using FFmpeg with a progress bar."""
    frame_files = sorted(glob(frame_dir + f'/colorized_frame_*_{model}.png'))
    total_frames = len(frame_files)

    command = f'ffmpeg -framerate {framerate} -i {frame_dir}/colorized_frame_%04d_{model}.png -c:v libx264 -pix_fmt yuv420p "{output_video}" -y -loglevel quiet'
    process = subprocess.Popen(command, shell=True)

    # Progress bar for video assembly
    with tqdm(total=total_frames, desc="Assembling video") as pbar:
        for _ in range(total_frames):
            pbar.update(1)
            time.sleep(0.01)
            
    process.wait()

def add_audio(original_video, colorized_video, final_output):
    """Add original audio to the colorized video using FFmpeg."""
    command = f'ffmpeg -i "{colorized_video}" -i "{original_video}" -c copy -map 0:v:0 -map 1:a:0 "{final_output}" -y -loglevel quiet'
    subprocess.run(command, shell=True)

def clean_up(directories):
    """Delete temporary directories."""
    for directory in directories:
        if os.path.exists(directory):
            shutil.rmtree(directory)

def main(input_video, output_video, model='eccv16', use_gpu=False):
    # Generate a unique timestamp for file naming
    unique_stamp = get_unique_stamp()

    # Create unique directories for frames and colorized frames
    frame_dir = f'./frames_{unique_stamp}'
    colorized_frame_dir = f'./colorized_frames_{unique_stamp}'

    # Step 1: Extract frames
    extract_frames(input_video, frame_dir)

    # Step 2: Colorize frames
    colorize_frames(frame_dir, colorized_frame_dir, model=model, use_gpu=use_gpu)

    # Step 3: Assemble colorized frames into a video
    colorized_video = f'colorized_output_{unique_stamp}.mp4'
    assemble_video(colorized_frame_dir, colorized_video, model=model)

    # Step 4: Add original audio back to the colorized video
    add_audio(input_video, colorized_video, output_video)

    # Step 5: Clean up temporary files
    clean_up([frame_dir, colorized_frame_dir])
    if os.path.exists(colorized_video):
        os.remove(colorized_video)

def cli():
    """Command-line interface for the vcolor tool."""
    parser = argparse.ArgumentParser(description="Video colorization tool using deep learning models.")
    parser.add_argument("-i", "--input", required=True, help="Path to the input video file.")
    parser.add_argument("-o", "--output", required=True, help="Path to the output video file.")
    parser.add_argument("-m", "--model", default="eccv16", choices=["eccv16", "siggraph17"], help="Colorization model to use.")
    parser.add_argument("--use_gpu", action="store_true", help="Enable GPU acceleration if supported.")

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()
    main(args.input, args.output, model=args.model, use_gpu=args.use_gpu)

if __name__ == "__main__":
    cli()