import os
import argparse
import video_processor
import processor
import config


def get_audio_source(video_file: str = None):
    if video_file and os.path.exists(video_file):
        try:
            audio_path = video_processor.extract_audio_from_video(video_file)
            return audio_path, True
        except Exception as e:
            print(f"\nERROR extracting audio from video: {e}")
            return None, False
    elif video_file:
        print(f"ERROR: Video file '{video_file}' not found.")
        return None, False
    elif os.path.exists(config.AUDIO_FILE):
        print(f"Using existing audio file: {config.AUDIO_FILE}")
        return config.AUDIO_FILE, False
    else:
        print(f"ERROR: No video file provided and audio file '{config.AUDIO_FILE}' not found.")
        return None, False


def ensure_output_dir():
    output_dir = "output"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    return output_dir


def save_transcript(transcript: list, output_file: str):
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(transcript))
    
    print("\n--- FINAL DELIVERABLE OUTPUT ---")
    print("\n".join(transcript))
    print(f"\nSUCCESS: Transcript saved to {output_file}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Transcribe video call and annotate with emotions and tones')
    parser.add_argument('video_file', nargs='?', help='Path to video file (.mp4)')
    parser.add_argument('-o', '--output', default='final_annotated_transcript.txt', 
                       help='Output filename (default: final_annotated_transcript.txt)')
    args = parser.parse_args()
    
    audio_path, temp_created = get_audio_source(args.video_file)
    
    if not audio_path:
        exit(1)
    
    try:
        transcript = processor.process_video_call(audio_path)
        
        output_dir = ensure_output_dir()
        output_path = os.path.join(output_dir, args.output)
        save_transcript(transcript, output_path)
        
        if temp_created and os.path.exists(audio_path):
            os.unlink(audio_path)
            print(f"Cleaned up temporary audio file: {audio_path}")
            
    except Exception as e:
        print(f"\nCRITICAL ERROR during execution: {e}")
        if temp_created and audio_path and os.path.exists(audio_path):
            os.unlink(audio_path)

