import os
import video_processor
import processor
import config


def get_audio_source():
    if os.path.exists(config.VIDEO_FILE):
        try:
            audio_path = video_processor.extract_audio_from_video(config.VIDEO_FILE)
            return audio_path, True
        except Exception as e:
            print(f"\nERROR extracting audio from video: {e}")
            return None, False
    elif os.path.exists(config.AUDIO_FILE):
        print(f"Using existing audio file: {config.AUDIO_FILE}")
        return config.AUDIO_FILE, False
    else:
        print(f"ERROR: Neither video file '{config.VIDEO_FILE}' nor audio file '{config.AUDIO_FILE}' found.")
        return None, False


def save_transcript(transcript: list, output_file: str):
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(transcript))
    
    print("\n--- FINAL DELIVERABLE OUTPUT ---")
    print("\n".join(transcript))
    print(f"\nSUCCESS: Transcript saved to {output_file}")


if __name__ == '__main__':
    audio_path, temp_created = get_audio_source()
    
    if not audio_path:
        exit(1)
    
    try:
        transcript = processor.process_video_call(audio_path)
        save_transcript(transcript, "final_annotated_transcript.txt")
        
        if temp_created and os.path.exists(audio_path):
            os.unlink(audio_path)
            print(f"Cleaned up temporary audio file: {audio_path}")
            
    except Exception as e:
        print(f"\nCRITICAL ERROR during execution: {e}")
        if temp_created and audio_path and os.path.exists(audio_path):
            os.unlink(audio_path)

