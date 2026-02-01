cask "ohh-brother" do
  version "0.1.0"
  sha256 :no_check  # TODO: Add actual sha256 after first release

  url "https://github.com/OWNER/ohh-brother/releases/download/v#{version}/Ohh-Brother-#{version}-mac.zip"
  name "Ohh Brother"
  desc "Passive meeting transcription with speaker diarization"
  homepage "https://github.com/OWNER/ohh-brother"

  app "Ohh Brother.app"

  postflight do
    # Remind user to set up Python environment
    ohai "Post-installation setup required:"
    ohai "  cd /Applications/Ohh\\ Brother.app/Contents/Resources/python"
    ohai "  python3 -m venv venv"
    ohai "  source venv/bin/activate"
    ohai "  pip install -r requirements.txt"
  end

  zap trash: [
    "~/Library/Application Support/OhhBrother",
    "~/Library/Preferences/com.ohhbrother.app.plist",
  ]
end
