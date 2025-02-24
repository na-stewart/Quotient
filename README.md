<!-- Improved compatibility of back to top link: See: https://github.com/othneildrew/Best-README-Template/pull/73 -->
<!--
*** Thanks for checking out the Best-README-Template. If you have a suggestion
*** that would make this better, please fork the repo and create a pull request
*** or simply open an issue with the tag "enhancement".
*** Don't forget to give the project a star!
*** Thanks again! Now go create something AMAZING! :D
-->

<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a>
    <img src="https://github.com/na-stewart/Quotient/blob/master/assets/logo.png" alt="Logo" width="350" height="350">
  </a>
</div>

<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li><a href="#about-the-project">About The Project</a></li>
    <li><a href="#installation">Usage</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
  </ol>
</details>

<!-- ABOUT THE PROJECT -->
## About The Project

Quotient is a financial insights tool designed to analyze and predict market movements based on SEC filings.
It scans regulatory 8-K documents to identify key financial signals, sentiment shifts, and potential market-moving events. 
Once Quotient identifies a potential lead, it will email a summary of the filing, impact analysis, and reference details.
This tool helps investors make decisions by extracting critical information from these filing, forecasting potential stock price movements.

<h6>NOT FINANCIAL ADVICE, CONDUCT YOUR OWN DUE DILIGENCE. Any investments, trades, speculations, or decisions made on 
the basis of any information, expressed or implied herein, are committed at your own risk, financial or otherwise.<h6>

<div>
  <img src="https://github.com/na-stewart/Quotient/blob/master/assets/preview2.PNG" alt="Image 2" width="500" height="450">
  <img src="https://github.com/na-stewart/Quotient/blob/master/assets/preview.PNG" alt="Image 1" width="300" height="450">
</div>

<!-- GETTING STARTED -->
## Usage

* Make desired changes to configuration in the `.env` file, below is an example of its contents:

```
EMAIL_LIST=example@email.com,example2@email.com
SEC_AGENT=me@example.com
SMTP_USERNAME=A98BBLFIUGE
SMTP_PASSWORD=29HWEFBLIWUG
SMTP_HOST=email-smtp.your-region.amazonaws.com
SMTP_FROM=noreply@example.com
DETERMINATION_PROMPT=Is this 8-K filing likely to impact the company's stock price? Only answer with 'yes' or 'no'.
EXPLANATION_PROMPT=How and why will this impact the company's stock price? Conclude with a bullish or bearish analysis.
VOLUME_THRESHOLD=20000000
MARKET_CAP_THRESHOLD=2260000000
TURNOVER_THRESHOLD=0.9
```

* Clone the repo
```sh
git clone https://github.com/na-stewart/Quotient
```

* Install Pip Packages
```sh
pip3 install -r requirements.txt
```

* Run quotient by simply double-clicking the `quotient.py` file or via command prompt.
```shell
python quotient.py
```

<!-- CONTRIBUTING -->
## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".
Don't forget to give the project a star! Thanks again!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<!-- LICENSE -->
## License

Distributed under the MIT License. See `LICENSE.txt` for more information.
